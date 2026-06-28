import base64
import hashlib
import json
import logging
import os
import re
import threading
import time
import traceback
from datetime import date
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI, APIError, APIConnectionError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ASA-Studio")

_shutdown_timer: threading.Timer | None = None
_shutdown_lock = threading.Lock()

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Trending cache
_trending_cache: list | None = None
_trending_fetched_at: float = 0
_trending_is_online: bool = False
_TRENDING_CACHE_TTL = 3600  # 1 hour

# ==================== Provider registry ====================
PROVIDERS = {
    "openai-compatible": {
        "name": "OpenAI 兼容 (Right Code 等)",
        "models": ["nano-banana", "nano-banana-2", "gpt-image-2", "gpt-image-2-vip", "nano-banana-pro"],
        "fields": ["base_url", "api_key"],
        "default_base_url": "https://www.right.codes/draw/v1",
    },
    "openai": {
        "name": "OpenAI DALL·E",
        "models": ["dall-e-3", "dall-e-2"],
        "fields": ["api_key"],
        "default_base_url": "",
    },
    "dashscope": {
        "name": "阿里百炼 通义万象",
        "models": ["wanx2.0-t2i-turbo", "wanx2.1-t2i-turbo", "wanx2.0-t2i-plus", "wanx2.0-cosplay"],
        "fields": ["api_key"],
        "default_base_url": "",
    },
    "stability": {
        "name": "Stability AI (Stable Diffusion)",
        "models": ["stable-diffusion-xl-1024-v1-0", "sd3.5-large", "sd3.5-medium", "core"],
        "fields": ["api_key"],
        "default_base_url": "",
    },
}

# ==================== Trending prompts ====================
TRENDING_PROMPTS = [
    # ── 爆款 ──
    {"zh": "潦草涂鸦风：用最笨拙潦草的方式重绘，白色背景，低质糟糕的离谱感", "en": "redraw in the clumsiest, messiest scribble style on white background, ridiculously bad quality", "cat": "爆款"},
    {"zh": "3D毛绒应用图标，柔软羊毛质感，柔和工作室灯光，可爱极简风格", "en": "3D fluffy app icon, plush wool texture with visible fibers, soft studio lighting, kawaii minimal style", "cat": "爆款"},
    {"zh": "AI小小分身：迷你3D Q版角色站在真实场景中，微缩模型效果", "en": "tiny 3D chibi character standing in a real-world scene, miniature diorama effect, tilt-shift photography", "cat": "爆款"},
    {"zh": "撕纸分层特效：画面被撕开露出底层线稿，多层次混合媒介", "en": "torn paper layered effect revealing line art underneath, mixed media, ripped edge revealing sketch", "cat": "爆款"},
    {"zh": "PS1复古游戏封面，低多边形风格，颗粒感纹理，怀旧游戏包装", "en": "PlayStation 1 retro game cover art, low-poly style, grainy texture, nostalgic game packaging", "cat": "爆款"},
    {"zh": "珐琅徽章风格，金属珐琅质感，硬朗轮廓，收藏级徽章设计", "en": "enamel pin design style, metallic enamel texture, hard enamel finish, collectible pin", "cat": "爆款"},
    {"zh": "吉卜力风格重绘：任何画面变成宫崎骏动画手绘风格", "en": "Studio Ghibli style redraw, hand-painted animation cel look, warm nostalgic lighting", "cat": "爆款"},
    {"zh": "黏土动画风格：塑料橡皮泥质感，定格动画人物，柔和灯光", "en": "claymation stop-motion style, plasticine texture, Aardman-inspired character, soft lighting", "cat": "爆款"},
    {"zh": "气球动物造型：用气球扭成各种形态，高光泽橡胶质感，白色背景", "en": "balloon animal sculpture, twisted balloon art, high gloss rubber texture, clean white background", "cat": "爆款"},
    {"zh": "霓虹灯艺术装置：文字或图案做成霓虹灯管，暗夜城市背景，发光效果", "en": "neon light art installation, glowing glass tubes, dark urban night background, luminous effect", "cat": "爆款"},
    # ── 电影感 ──
    {"zh": "赛博朋克都市夜景，霓虹灯倒映在湿漉漉的街道，35mm胶片质感", "en": "cyberpunk city at night, neon reflections on wet pavement, shot on 35mm film, Blade Runner aesthetic", "cat": "电影感"},
    {"zh": "电影级肖像，伦勃朗布光，大光圈浅景深，柯达胶片调色", "en": "cinematic portrait, Rembrandt lighting, wide aperture shallow depth of field, Kodak Portra 400 color grading", "cat": "电影感"},
    {"zh": "黄金时刻的草原奔跑，体积雾，逆光剪影，电影画幅2.35:1", "en": "running through grassland at golden hour, volumetric fog, backlit silhouette, anamorphic 2.35:1", "cat": "电影感"},
    {"zh": "雨中东京街头，霓虹招牌倒影，透明雨伞，胶片颗粒感", "en": "rainy Tokyo street at night, neon sign reflections, transparent umbrellas, film grain, cinematic mood", "cat": "电影感"},
    {"zh": "王家卫风格：霓虹灯光、动态模糊、绿色调、情绪化独白氛围", "en": "Wong Kar-wai cinematic style, neon glow, motion blur, green color cast, melancholic atmosphere", "cat": "电影感"},
    {"zh": "韦斯安德森对称构图，粉彩色调，精心布置的场景，正面视角", "en": "Wes Anderson symmetrical composition, pastel color palette, meticulously arranged scene, frontal perspective", "cat": "电影感"},
    {"zh": "无人机俯拍城市夜景，万家灯火，车流如织长曝光，电影感色调", "en": "drone aerial night cityscape, sea of lights, long exposure traffic trails, cinematic color grade", "cat": "电影感"},
    {"zh": "西部牛仔对峙场景，日落逆光剪影，漫天黄沙，宽银幕电影感", "en": "western cowboy standoff at sunset, backlit silhouettes, dusty desert atmosphere, widescreen cinematic", "cat": "电影感"},
    {"zh": "希区柯克式变焦镜头，主体清晰背景拉远，悬疑氛围，黑白电影感", "en": "Hitchcock dolly zoom effect, subject sharp background receding, suspenseful atmosphere, black and white", "cat": "电影感"},
    {"zh": "水下摄影电影感，阳光从水面穿透，漂浮的裙摆，蓝色调静谧氛围", "en": "underwater cinematic photography, sun rays penetrating water surface, floating fabric, serene blue tones", "cat": "电影感"},
    # ── 设计 ──
    {"zh": "极简品牌Logo设计，几何抽象，2-3色搭配，干净线条可缩放矢量", "en": "minimalist logo design, geometric abstract, 2-3 color palette, clean lines, scalable vector style", "cat": "设计"},
    {"zh": "精品咖啡包装设计，哑光黑色袋子，铜箔烫印，现代工匠美学", "en": "premium coffee bag packaging, matte black pouch, copper foil stamping, modern artisan aesthetic", "cat": "设计"},
    {"zh": "App Store截图背景，光滑渐变，玻璃拟态，冷静蓝白调，大量留白", "en": "App Store screenshot background, smooth gradients, glassmorphism shapes, calm blue and white palette", "cat": "设计"},
    {"zh": "现代品牌情绪板，柔和中性色，温暖晨光，极简室内，天然纹理", "en": "moodboard for modern wellness brand, soft neutral colors, warm morning light, minimalist interiors", "cat": "设计"},
    {"zh": "奢侈品香水瓶设计，水晶切割面，金色细节，白色大理石底座", "en": "luxury perfume bottle design, crystal facets, gold accents, white marble base, product photography", "cat": "设计"},
    {"zh": "日式文具品牌VI设计，手绘水彩元素，柔和米色调，精致排版", "en": "Japanese stationery brand identity, hand-painted watercolor elements, soft beige tones, elegant typography", "cat": "设计"},
    {"zh": "科技产品发布会邀请函设计，全息镭射质感，深邃黑底，未来感", "en": "tech product launch invitation design, holographic foil texture, deep black background, futuristic", "cat": "设计"},
    {"zh": "精酿啤酒罐身插画，涂鸦手绘风格，鲜艳配色，街头艺术感", "en": "craft beer can illustration, graffiti hand-drawn style, vibrant colors, street art vibe", "cat": "设计"},
    {"zh": "专辑封面设计，实验性排版，噪点纹理，复古CD质感，独立音乐风格", "en": "album cover art design, experimental typography, grain texture, retro CD packaging, indie music aesthetic", "cat": "设计"},
    {"zh": "UI/UX界面设计展示，暗色模式仪表盘，数据可视化，玻璃拟态，霓虹高亮", "en": "UI/UX dashboard design showcase, dark mode, data visualization, glassmorphism, neon accent highlights", "cat": "设计"},
    # ── 摄影 ──
    {"zh": "专业美食摄影，俯拍角度，自然日光，浅景深，美食杂志质感", "en": "professional food photography, overhead flat lay, natural daylight, shallow depth of field, food magazine quality", "cat": "摄影"},
    {"zh": "商业产品摄影，大理石表面，柔光棚拍，超写实，8K分辨率", "en": "commercial product photography on marble surface, soft diffused studio lighting, hyperrealistic, 8K resolution", "cat": "摄影"},
    {"zh": "航拍自然风光，鸟瞰视角，清晨薄雾，阳光穿过云层，国家地理风格", "en": "aerial nature landscape, bird's eye view, morning mist, sun rays through clouds, National Geographic style", "cat": "摄影"},
    {"zh": "微距昆虫摄影，露珠细节，焦外散景，100mm微距镜头", "en": "macro insect photography, dewdrop details, creamy bokeh, 100mm macro lens, extreme detail", "cat": "摄影"},
    {"zh": "黑白街头摄影，强烈光影对比，决定性瞬间，布列松风格", "en": "black and white street photography, strong light and shadow contrast, decisive moment, Cartier-Bresson style", "cat": "摄影"},
    {"zh": "极光夜空摄影，冰岛冰湖倒映极光，满月，广角星空", "en": "aurora borealis night photography, Icelandic glacier lagoon reflection, full moon, wide angle astrophotography", "cat": "摄影"},
    {"zh": "婚礼纪实摄影，自然光窗边，新娘准备瞬间，温柔暖黄色调", "en": "wedding documentary photography, natural window light, bride preparation moment, soft warm tones", "cat": "摄影"},
    {"zh": "体育动作高速摄影，篮球扣篮瞬间，汗水飞溅，体育场灯光", "en": "sports action high-speed photography, basketball dunk moment, sweat droplets, stadium dramatic lighting", "cat": "摄影"},
    {"zh": "宠物肖像摄影，黑色背景，单灯布光，狗狗表情特写，影棚质感", "en": "pet portrait photography, black background, single studio light, dog expression close-up, professional quality", "cat": "摄影"},
    {"zh": "老式胶片漏光效果，日系清新色调，夏日海滩记忆，90年代胶片相机", "en": "vintage film light leak effect, Japanese fresh color tone, summer beach memory, 90s point-and-shoot aesthetic", "cat": "摄影"},
    # ── 插画 ──
    {"zh": "宫崎骏风格动画场景，温暖色调，手绘质感，梦幻天空之城", "en": "Studio Ghibli style animated scene, warm color palette, hand-painted texture, dreamy floating castle", "cat": "插画"},
    {"zh": "水墨画风格山水，大面积留白，干笔飞白，诗意意境", "en": "ink wash painting landscape, large negative space, dry brush texture, poetic atmosphere, Chinese sumi-e style", "cat": "插画"},
    {"zh": "浮世绘风格海浪，葛饰北斋灵感，木板印刷质感，靛蓝色调", "en": "ukiyo-e style ocean wave, Hokusai inspired, woodblock print texture, indigo blue tones", "cat": "插画"},
    {"zh": "蒸汽波美学，CRT显示器光晕，VHS噪点，粉紫渐变，80年代字体", "en": "vaporwave aesthetic, CRT monitor glow, VHS noise, pink and purple gradient, 1980s typography", "cat": "插画"},
    {"zh": "治愈系手绘水彩，小狐狸在花丛中，柔和暖色，儿童绘本风格", "en": "cozy watercolor illustration, little fox among wildflowers, soft warm colors, children's book style", "cat": "插画"},
    {"zh": "美式复古漫画封面，网点纸纹理，粗犷线条，超级英雄动态姿势", "en": "vintage American comic book cover, halftone dots texture, bold outlines, superhero dynamic pose", "cat": "插画"},
    {"zh": "装饰艺术风格插画，几何图形，金箔质感，1920年代奢华美学", "en": "Art Deco illustration style, geometric patterns, gold leaf texture, 1920s luxury aesthetic", "cat": "插画"},
    {"zh": "数字绘画厚涂风格，女战士角色设计，金属盔甲细节，史诗感", "en": "digital painting thick paint style, female warrior character design, detailed metal armor, epic atmosphere", "cat": "插画"},
    {"zh": "莫比斯风格的科幻场景，精细线条，平涂色彩，异星世界探索", "en": "Moebius style sci-fi landscape, fine linework, flat colors, alien world exploration", "cat": "插画"},
    {"zh": "波普艺术风格，复刻安迪沃霍尔丝网印刷，鲜艳色彩重复排列", "en": "pop art style, Andy Warhol inspired silkscreen print, vibrant colors repeated arrangement", "cat": "插画"},
    # ── 3D ──
    {"zh": "3D玻璃材质抽象雕塑，次表面散射，柔光工作室环境，8K渲染", "en": "3D glass abstract sculpture, subsurface scattering, soft studio lighting, Octane render, 8K", "cat": "3D"},
    {"zh": "低多边形等距房间，柔和配色，游戏资产风格，Blender渲染", "en": "low poly isometric room, pastel color palette, game asset style, cozy vibes, Blender render", "cat": "3D"},
    {"zh": "数字花卉超现实景观，柔和雾化失焦，浪漫粉彩调色板", "en": "digital surreal botanical landscape, soft hazy out-of-focus, romantic pastel palette, dreamlike garden", "cat": "3D"},
    {"zh": "迷幻超现实混合纹理，2D与3D层叠深度，光学错觉，柔和霓虹", "en": "psychedelic surrealism, mixed 2D and 3D textures, layered depth, optical illusions, soft neon tones", "cat": "3D"},
    {"zh": "3D像素艺术场景，体素风格，等距视角，可爱的森林小镇", "en": "3D pixel art scene, voxel style, isometric view, cute forest village, vibrant colors", "cat": "3D"},
    {"zh": "未来主义交通工具概念设计，流线型车身，全息HUD界面展示", "en": "futuristic vehicle concept design, streamlined body, holographic HUD interface display, 8K", "cat": "3D"},
    {"zh": "C4D卡通角色设计，圆润造型，糖果配色，趣味表情，盲盒玩具风格", "en": "C4D cartoon character design, rounded shapes, candy colors, fun expression, blind box toy style", "cat": "3D"},
    {"zh": "赛博朋克风格3D房间，全息广告牌窗外，霓虹灯光照入，游戏场景", "en": "cyberpunk 3D room interior, holographic billboards outside window, neon lights spilling in, game environment", "cat": "3D"},
    {"zh": "3D图标组，拟物化风格，柔和阴影，浅色背景，UI设计用途", "en": "3D icon set, skeuomorphic style, soft shadows, light background, UI design assets", "cat": "3D"},
    {"zh": "抽象3D流体艺术，金属液态汞效果，PBR材质，超写实渲染", "en": "abstract 3D fluid art, liquid mercury metallic effect, PBR material, photorealistic render", "cat": "3D"},
    # ── 时尚 ──
    {"zh": "高级时装编辑摄影，模特穿着前卫设计，戏剧性光影，杂志质感", "en": "haute couture editorial photo, avant-garde fashion, dramatic lighting, magazine quality", "cat": "时尚"},
    {"zh": "老钱风暗黑女性气场，和服改良版，Quiet Luxury，低调奢华", "en": "quiet luxury dark feminine aesthetic, modern kimono, old money style, understated elegance", "cat": "时尚"},
    {"zh": "日系清新写真，自然光，胶片色调，少女感，夏日氛围", "en": "Japanese fresh style portrait, natural lighting, film tone color grading, summer vibes", "cat": "时尚"},
    {"zh": "赛博朋克街头时尚，LED发光服饰，透明PVC面料，未来东京街头", "en": "cyberpunk street fashion, LED illuminated clothing, transparent PVC fabric, futuristic Tokyo street", "cat": "时尚"},
    {"zh": "复古90年代时尚大片，胶片颗粒，暖黄色调，超模在纽约街头", "en": "retro 90s fashion editorial, film grain, warm yellow tones, supermodel on NYC streets", "cat": "时尚"},
    {"zh": "汉服国风时尚摄影，敦煌飞天灵感，飘逸丝绸，沙漠自然光", "en": "Chinese hanfu fashion photography, Dunhuang flying celestial inspiration, flowing silk, desert natural light", "cat": "时尚"},
    {"zh": "极简主义时尚造型，黑白灰配色，建筑感廓形，现代舞者姿态", "en": "minimalist fashion editorial, black white grey palette, architectural silhouette, modern dancer pose", "cat": "时尚"},
    {"zh": "维多利亚时代复古蕾丝洋装，古典花园场景，柔和漫射光，油画质感", "en": "Victorian era vintage lace dress, classical garden setting, soft diffused light, oil painting texture", "cat": "时尚"},
    {"zh": "街头潮流运动鞋特写，霓虹灯反射在漆皮鞋面，赛博朋克都市色调", "en": "streetwear sneaker close-up, neon lights reflecting on patent leather, cyberpunk urban color grading", "cat": "时尚"},
    {"zh": "波西米亚度假风，飘逸长裙，海风吹拂，黄金时刻逆光，自由灵魂", "en": "bohemian vacation style, flowing maxi dress, sea breeze, golden hour backlight, free spirit", "cat": "时尚"},
    # ── 建筑 ──
    {"zh": "现代极简主义建筑外观，大面积玻璃幕墙，黄金时刻光影", "en": "modern minimalist architecture exterior, large glass curtain wall, golden hour lighting, architectural photography", "cat": "建筑"},
    {"zh": "侘寂风格室内设计，天然材料，柔和光线，平静氛围，绿植点缀", "en": "wabi-sabi interior design, natural materials, soft diffused light, calm atmosphere, indoor plants", "cat": "建筑"},
    {"zh": "扎哈风格参数化建筑，流动曲线，白色混凝土，未来城市地标", "en": "Zaha Hadid style parametric architecture, flowing curves, white concrete, futuristic city landmark", "cat": "建筑"},
    {"zh": "苏州园林一角，月洞门框景，白墙黛瓦，雨後青苔，诗意空间", "en": "Suzhou classical garden corner, moon gate framing view, white walls grey tiles, moss after rain, poetic space", "cat": "建筑"},
    {"zh": "北欧风格客厅，原木地板，白色墙面，极简家具，充足自然光", "en": "Scandinavian style living room, oak wooden floor, white walls, minimalist furniture, abundant natural light", "cat": "建筑"},
    {"zh": "哥特式大教堂内部，高耸穹顶，彩色玻璃玫瑰窗，神圣光束", "en": "Gothic cathedral interior, soaring vaulted ceiling, stained glass rose window, divine light beams", "cat": "建筑"},
    {"zh": "日式传统茶室，障子纸门，榻榻米，窗外枯山水庭园，静谧禅意", "en": "Japanese traditional tea room, shoji paper doors, tatami mats, dry landscape garden view, zen tranquility", "cat": "建筑"},
    {"zh": "热带雨林树屋建筑设计，竹木结构，全景落地窗，融入自然", "en": "tropical rainforest treehouse architecture, bamboo timber structure, panoramic floor-to-ceiling windows, nature integration", "cat": "建筑"},
    {"zh": "野兽派粗野主义建筑，裸露混凝土，几何体块，阴天氛围，建筑摄影", "en": "brutalist architecture, exposed raw concrete, geometric massing, overcast atmosphere, architectural photography", "cat": "建筑"},
    {"zh": "赛博朋克垂直城市，九龙城寨风格密集建筑群，霓虹招牌层叠，雨夜", "en": "cyberpunk vertical city, Kowloon Walled City style dense architecture, layered neon signs, rainy night", "cat": "建筑"},
    # ── 奇幻 ──
    {"zh": "史诗级奇幻场景，漂浮岛屿，瀑布倾泻入云海，魔法光效，壮观", "en": "epic fantasy landscape, floating islands, waterfalls cascading into clouds, magical glow, breathtaking", "cat": "奇幻"},
    {"zh": "怀旧未来主义，液态金属，全息箔，像素艺术，酸性色彩，Y2K复兴", "en": "retro-futurism, liquid metal surfaces, holographic foil, pixel art elements, acid colors, Y2K revival", "cat": "奇幻"},
    {"zh": "科幻太空站内部，巨大观景窗俯瞰星云，极简工业设计，电影级光照", "en": "sci-fi space station interior, massive viewing window overlooking nebula, cinematic lighting", "cat": "奇幻"},
    {"zh": "中土世界风格精灵森林，巨树发光，萤火虫飞舞，魔法苔藓，梦幻", "en": "Middle-earth style elven forest, giant glowing trees, fireflies dancing, magical moss, dreamlike", "cat": "奇幻"},
    {"zh": "蒸汽朋克飞艇城市，齿轮与黄铜，维多利亚时代科幻，云层之上海港", "en": "steampunk airship city, gears and brass, Victorian era sci-fi, sky harbor above clouds", "cat": "奇幻"},
    {"zh": "赛博朋克2077风格夜城，巨型全息广告，改造人路人，雨夜霓虹", "en": "Cyberpunk 2077 style night city, giant holographic ads, cybernetic pedestrians, rainy neon night", "cat": "奇幻"},
    {"zh": "中国神话仙境，仙鹤飞过金色祥云，远处漂浮仙山，祥瑞光芒", "en": "Chinese mythical celestial realm, cranes flying through golden clouds, distant floating mountains, auspicious light", "cat": "奇幻"},
    {"zh": "克苏鲁风格深海恐怖，巨大触手从深渊升起，水手小船渺小对比", "en": "Lovecraftian deep sea horror, massive tentacles rising from abyss, tiny sailor boat for scale, dark atmosphere", "cat": "奇幻"},
    {"zh": "精灵宝可梦风格世界，训练师与伙伴在广阔草原，阳光明媚冒险", "en": "Pokemon style world, trainer and companion on vast grassland, sunny adventure atmosphere", "cat": "奇幻"},
    {"zh": "废土末日世界，废弃城市被自然回收，孤独幸存者眺望远方", "en": "post-apocalyptic wasteland world, abandoned city reclaimed by nature, lone survivor gazing at distance", "cat": "奇幻"},
    # ── 治愈 ──
    {"zh": "可爱柴犬戴着毛线帽，柔和粉彩背景，3D毛绒质感，治愈系", "en": "cute Shiba Inu wearing knitted beanie, soft pastel background, 3D fluffy texture, kawaii", "cat": "治愈"},
    {"zh": "猫咪咖啡馆水彩插画，温暖舒适氛围，手绘线条，淡雅配色", "en": "cat cafe watercolor illustration, warm cozy atmosphere, hand-drawn lines, light elegant color palette", "cat": "治愈"},
    {"zh": "小熊猫抱着竹子睡觉，柔和阳光透过树叶，毛茸茸细节，温馨治愈", "en": "red panda sleeping hugging bamboo, soft sunlight through leaves, fluffy fur details, heartwarming", "cat": "治愈"},
    {"zh": "窗边读书的猫咪，下雨天，毛毯和热茶，温暖室内光，挪威森林猫", "en": "cat reading by window, rainy day, cozy blanket and hot tea, warm indoor lighting, Norwegian Forest Cat", "cat": "治愈"},
    {"zh": "面包店橱窗水彩，新鲜出炉的牛角包，晨光透过玻璃，温暖香气感", "en": "bakery window watercolor, freshly baked croissants, morning light through glass, warm aromatic feeling", "cat": "治愈"},
    {"zh": "花园里的小刺猬，蘑菇帽子，露珠细节，微观世界，童话风格", "en": "little hedgehog in garden, mushroom hat, dewdrop details, micro world, fairy tale style", "cat": "治愈"},
    {"zh": "海边日出瑜伽，女性剪影，平静海面倒映朝霞，心灵治愈氛围", "en": "sunrise beach yoga, female silhouette, calm ocean reflecting dawn sky, spiritual healing atmosphere", "cat": "治愈"},
    {"zh": "星空下的帐篷营地，篝火微光，银河清晰可见，露营治愈夜晚", "en": "starry night tent camping, campfire glow, Milky Way clearly visible, cozy outdoor healing night", "cat": "治愈"},
    {"zh": "老奶奶编织毛衣，摇椅上打盹的猫，午后阳光，怀旧温暖回忆", "en": "grandmother knitting sweater, cat napping on rocking chair, afternoon sunlight, nostalgic warm memory", "cat": "治愈"},
    {"zh": "薰衣草花田日落，紫色海洋随风起伏，少女背影漫步其中，治愈系", "en": "lavender field at sunset, purple sea swaying in breeze, girl's silhouette walking, healing vibes", "cat": "治愈"},
    # ── 国风 ──
    {"zh": "千里江山图风格青绿山水，金色线条勾勒，宋代美学意境", "en": "A Thousand Li of Rivers and Mountains style blue-green landscape, gold line outlines, Song dynasty aesthetics", "cat": "国风"},
    {"zh": "敦煌飞天壁画风格，飘逸彩带，莲花座，金色赭石色调", "en": "Dunhuang flying celestial mural style, flowing ribbons, lotus throne, golden ochre color palette", "cat": "国风"},
    {"zh": "工笔花鸟画，精细勾勒，淡彩渲染，绢本质感，宋徽宗风格", "en": "meticulous Chinese gongbi flower-and-bird painting, fine outlines, light color wash, silk texture", "cat": "国风"},
    {"zh": "武侠小说封面插画，侠客立于山巅，衣袂飘飘，明月当空", "en": "wuxia novel cover illustration, swordsman standing on mountain peak, robes flowing in wind, bright full moon", "cat": "国风"},
    {"zh": "皮影戏风格，镂空剪影效果，暖黄灯光透射，传统民俗艺术", "en": "Chinese shadow puppetry style, cutout silhouette effect, warm yellow light transmission, traditional folk art", "cat": "国风"},
    {"zh": "青花瓷图案设计，蓝白配色，缠枝莲纹，景德镇瓷器美学", "en": "blue and white porcelain pattern design, cobalt blue on white, scrolling lotus motifs, Jingdezhen ceramic aesthetic", "cat": "国风"},
    {"zh": "水墨动画风格竹林，大熊猫嬉戏，雾气缭绕，电影级构图", "en": "ink wash animation style bamboo forest, giant pandas playing, misty atmosphere, cinematic composition", "cat": "国风"},
    {"zh": "汉服女子在樱花树下，花瓣飘落，唐风襦裙，古典美人画", "en": "hanfu lady under cherry blossom tree, petals falling, Tang dynasty style dress, classical beauty painting", "cat": "国风"},
    {"zh": "京剧脸谱艺术设计，浓烈色彩，对称构图，舞台灯光效果", "en": "Beijing opera facial makeup art design, intense colors, symmetrical composition, stage lighting effect", "cat": "国风"},
    {"zh": "古镇雨巷夜景，红灯笼倒影青石板路，油纸伞背影，江南水乡", "en": "ancient town rainy alley at night, red lanterns reflecting on stone path, oil paper umbrella silhouette, Jiangnan water town", "cat": "国风"},
    # ── 抽象 ──
    {"zh": "康定斯基风格抽象画，几何圆形与线条，原色搭配，音乐感构图", "en": "Kandinsky style abstract painting, geometric circles and lines, primary colors, musical composition", "cat": "抽象"},
    {"zh": "罗斯科色域绘画风格，大块柔和色彩叠加，冥想氛围，美术馆灯光", "en": "Rothko color field painting style, large soft color blocks layered, meditative atmosphere, gallery lighting", "cat": "抽象"},
    {"zh": "液体丙烯泼洒艺术，细胞结构纹理，鲜艳色彩，宏观摄影", "en": "fluid acrylic pour art, cellular structure texture, vibrant colors, macro photography", "cat": "抽象"},
    {"zh": "极简黑白几何构成，蒙德里安风格，红黄蓝方块，网格结构", "en": "minimalist black and white geometric composition, Mondrian style, red yellow blue squares, grid structure", "cat": "抽象"},
    {"zh": "数据故障艺术，像素排序，色彩通道分离，数字失真美学", "en": "datamosh glitch art, pixel sorting, color channel separation, digital distortion aesthetic", "cat": "抽象"},
    {"zh": "大理石纹路抽象画，流动的墨水在水中，慢动作摄影捕捉", "en": "marble pattern abstract art, flowing ink in water, slow motion photography capture", "cat": "抽象"},
    {"zh": "声波可视化艺术，音乐频率转换成色彩波纹，深色背景，发光线条", "en": "sound wave visualization art, music frequencies as colorful ripples, dark background, glowing lines", "cat": "抽象"},
    {"zh": "分形艺术曼德勃罗集，无限递归细节，迷幻色彩，数学之美", "en": "fractal art Mandelbrot set, infinite recursive detail, psychedelic colors, beauty of mathematics", "cat": "抽象"},
    # ── 游戏 ──
    {"zh": "像素风RPG游戏场景，16-bit风格，俯视视角，村庄地图设计", "en": "pixel art RPG game scene, 16-bit style, top-down view, village map design", "cat": "游戏"},
    {"zh": "黑暗之魂风格游戏场景，破败城堡，雾门，史诗Boss战场地", "en": "Dark Souls style game environment, ruined castle, fog gate, epic boss arena", "cat": "游戏"},
    {"zh": "动物森友会风格小岛，可爱动物村民，秋天枫叶，DIY工作台", "en": "Animal Crossing style island, cute animal villagers, autumn maple leaves, DIY workbench", "cat": "游戏"},
    {"zh": "极乐迪斯科风格肖像画，表现主义油画质感，忧郁色调，内心独白", "en": "Disco Elysium style portrait, expressionist oil painting texture, melancholic tones, inner monologue feel", "cat": "游戏"},
    {"zh": "塞尔达风格开放世界，草原与远山，滑翔伞视角，冒险氛围", "en": "Zelda style open world, grasslands and distant mountains, paraglider view, adventure atmosphere", "cat": "游戏"},
    {"zh": "生化奇兵水下城市，装饰艺术建筑，发亮的水母，乌托邦破败感", "en": "BioShock underwater city, Art Deco architecture, glowing jellyfish, utopian decay atmosphere", "cat": "游戏"},
    {"zh": "空洞骑士风格地下王国，手绘2D美术，蓝紫色调，萤火虫光源", "en": "Hollow Knight style underground kingdom, hand-drawn 2D art, blue-purple tones, firefly light sources", "cat": "游戏"},
    {"zh": "对马岛之魂风格，武士站在枫树下，红色落叶，黑白电影模式", "en": "Ghost of Tsushima style, samurai under maple tree, red falling leaves, Kurosawa black and white mode", "cat": "游戏"},
    # ── 人物 ──
    {"zh": "老人肖像，每一条皱纹诉说着故事，黑白高对比度，纪实风格", "en": "elderly person portrait, every wrinkle tells a story, black and white high contrast, documentary style", "cat": "人物"},
    {"zh": "双胞胎姐妹对称肖像，同一张脸不同表情，镜子反射，伦勃朗光", "en": "twin sisters symmetrical portrait, same face different expressions, mirror reflection, Rembrandt lighting", "cat": "人物"},
    {"zh": "舞者在空中定格，芭蕾舞裙飘扬，黑色背景，高速闪光捕捉", "en": "dancer frozen mid-air, ballet tutu floating, black background, high-speed flash capture", "cat": "人物"},
    {"zh": "少数民族传统服饰肖像，银饰细节，自然光线，文化传承感", "en": "ethnic minority traditional costume portrait, silver ornament details, natural lighting, cultural heritage feel", "cat": "人物"},
    {"zh": "未来战士概念角色设计，外骨骼装甲，全息头盔，科幻军武风", "en": "futuristic soldier concept character design, exoskeleton armor, holographic helmet, sci-fi military style", "cat": "人物"},
    {"zh": "瑜伽修行者在山巅冥想，晨光破晓，云雾环绕，灵性觉醒", "en": "yoga practitioner meditating on mountain peak, dawn breaking, mist surrounding, spiritual awakening", "cat": "人物"},
    # ── 自然 ──
    {"zh": "冰岛黑沙滩与冰晶，蓝冰洞内部，自然纹理，国家地理风格", "en": "Iceland black sand beach with ice crystals, blue ice cave interior, natural textures, National Geographic style", "cat": "自然"},
    {"zh": "撒哈拉沙漠星空延时效果，银河拱桥，孤树剪影，宇宙渺小感", "en": "Sahara desert starry night long exposure, Milky Way arch, lone tree silhouette, cosmic insignificance", "cat": "自然"},
    {"zh": "樱花季京都岚山，竹林小径，樱花雨飘落，春日光影", "en": "cherry blossom season Kyoto Arashiyama, bamboo grove path, sakura petals falling, spring sunlight", "cat": "自然"},
    {"zh": "火山喷发闪电奇观，熔岩流淌，火山灰云中闪电交织，自然之力", "en": "volcanic eruption lightning phenomenon, lava flow, lightning in ash cloud, raw power of nature", "cat": "自然"},
    {"zh": "挪威峡湾极光之夜，雪山倒影宁静水面，绿色极光舞动", "en": "Norwegian fjord aurora night, snow mountains reflecting in calm water, green northern lights dancing", "cat": "自然"},
    {"zh": "亚马逊热带雨林俯拍，河流蜿蜒如蛇，浓郁绿色层次，地球之肺", "en": "Amazon rainforest aerial view, river winding like snake, rich green layers, lungs of the Earth", "cat": "自然"},
    {"zh": "深海生物发光奇观，水母群发出蓝色荧光，黑暗深海，异星般美丽", "en": "deep sea bioluminescence spectacle, jellyfish swarm glowing blue, dark ocean depths, alien beauty", "cat": "自然"},
    {"zh": "蒲公英微距摄影，种子即将飞散，逆光半透明冠毛，春天细节", "en": "dandelion macro photography, seeds about to disperse, backlit translucent pappus, spring detail", "cat": "自然"},
    {"zh": "纳米布沙漠红色沙丘，枯树死亡谷，橙色与蓝色对比，超现实自然", "en": "Namib desert red sand dunes, dead trees in Deadvlei, orange and blue contrast, surreal nature", "cat": "自然"},
    {"zh": "秋日枫林隧道，阳光穿透红叶，地面铺满落叶，温暖金色调", "en": "autumn maple tree tunnel, sunlight piercing red leaves, ground covered in fallen leaves, warm golden tones", "cat": "自然"},
]

def get_daily_trending() -> list[dict]:
    today_str = date.today().isoformat()
    seed = int(hashlib.md5(today_str.encode()).hexdigest(), 16)
    rng = __import__("random").Random(seed)
    indices = rng.sample(range(len(TRENDING_PROMPTS)), min(12, len(TRENDING_PROMPTS)))
    return [TRENDING_PROMPTS[i] for i in indices]


def _detect_category(prompt: str) -> str:
    p = prompt.lower()
    cats = [
        (["anime", "manga", "waifu", "cartoon", "ghibli", "illustration", "drawing", "sketch", "watercolor", "ink", "ukiyo", "comic", "manga"], "插画"),
        (["photorealistic", "photograph", "realistic", "8k", "cinematic", "portrait", "film", "bokeh", "macro", "telephoto"], "摄影"),
        (["cyberpunk", "sci-fi", "fantasy", "magic", "dragon", "warrior", "alien", "dystopian", "steampunk"], "奇幻"),
        (["landscape", "nature", "mountain", "ocean", "forest", "sunset", "sky", "garden", "river"], "风景"),
        (["architecture", "building", "interior", "design room", "facade"], "建筑"),
        (["3d", "render", "octane", "blender", "unreal", "c4d", "3d model", "isometric"], "3D"),
        (["logo", "ui", "icon", "branding", "minimalist", "flat design", "vector"], "设计"),
        (["fashion", "outfit", "dress", "model shoot", "runway", "style"], "时尚"),
        (["food", "cooking", "dish", "cuisine", "meal", "dessert", "drink"], "美食"),
        (["cat", "dog", "animal", "cute", "kawaii", "chibi", "fluffy", "pet", "baby"], "治愈"),
    ]
    for keywords, cat in cats:
        if any(k in p for k in keywords):
            return cat
    return "综合"


def fetch_online_trending(force: bool = False) -> list[dict]:
    global _trending_cache, _trending_fetched_at, _trending_is_online

    if not force and _trending_cache is not None:
        if time.time() - _trending_fetched_at < _TRENDING_CACHE_TTL:
            return _trending_cache

    sources = [
        {
            "name": "CivitAI",
            "url": "https://civitai.com/api/v1/images",
            "params": {"sort": "Most Reactions", "period": "Day", "limit": 30, "nsfw": "None"},
        },
    ]

    for src in sources:
        try:
            logger.info(f"Fetching trending from {src['name']}...")
            resp = httpx.get(
                src["url"],
                params=src["params"],
                timeout=20.0,
                headers={"User-Agent": "ASA-Studio/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            logger.info(f"{src['name']} returned {len(items)} items")

            prompts = []
            seen = set()
            for item in items:
                meta = item.get("meta") or {}
                prompt = (meta.get("prompt") or "").strip()
                if not prompt or len(prompt) < 10:
                    continue
                key = prompt[:60]
                if key in seen:
                    continue
                seen.add(key)
                short = prompt if len(prompt) <= 200 else prompt[:200] + "..."
                zh = prompt if len(prompt) <= 80 else prompt[:80] + "…"
                cat = _detect_category(prompt)
                image_id = item.get("id", "")
                src_url = f"https://civitai.com/images/{image_id}" if image_id else ""
                prompts.append({"zh": zh, "en": short, "cat": cat, "src_url": src_url})
                if len(prompts) >= 12:
                    break

            logger.info(f"{src['name']}: {len(prompts)} valid prompts extracted")
            if len(prompts) >= 3:
                _trending_cache = prompts
                _trending_fetched_at = time.time()
                _trending_is_online = True
                return prompts
        except Exception as e:
            logger.warning(f"Trending source '{src['name']}' failed: {e}")
            continue

    logger.info("All online sources failed, using static fallback")
    _trending_is_online = False
    return get_daily_trending()


# ==================== Request models ====================
class GenerateRequest(BaseModel):
    provider: str
    prompt: str
    size: str = "1024x1024"
    model: str = ""
    api_key: str
    base_url: str = ""
    image_b64: str | None = None

class TestRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str = ""

# ==================== Helpers ====================
def normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")

def extract_image_urls(text: str) -> list[str]:
    urls = []
    urls.extend(re.findall(r"!\[.*?\]\((https?://[^\s)]+)\)", text))
    urls.extend(re.findall(r"(https?://[^\s]+\.(?:png|jpg|jpeg|gif|webp))", text, re.I))
    return urls

def save_image(b64: str, prompt: str) -> str:
    ts = int(time.time())
    safe_name = re.sub(r"[\s\\/:*?\"<>|]", "_", prompt)
    safe_name = re.sub(r"[^\w一-鿿_-]", "", safe_name)
    safe_name = safe_name[:50]
    fname = f"{ts}_{safe_name}.png"
    (OUTPUT_DIR / fname).write_bytes(base64.b64decode(b64))
    return fname

# ==================== Provider: OpenAI-compatible chat ====================
def generate_openai_compatible(req: GenerateRequest) -> dict:
    base_url = normalize_base_url(req.base_url)
    http_client = httpx.Client(timeout=120.0)
    client = OpenAI(api_key=req.api_key, base_url=base_url, http_client=http_client)

    if req.image_b64:
        content = [
            {"type": "text", "text": req.prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{req.image_b64}"}},
        ]
    else:
        content = req.prompt

    try:
        resp = client.chat.completions.create(
            model=req.model,
            messages=[{"role": "user", "content": content}],
            max_tokens=2000,
        )
        text = resp.choices[0].message.content or ""
    except APIConnectionError as e:
        raise HTTPException(status_code=502, detail=f"网络连接失败: {e}")
    except APIError as e:
        raise HTTPException(status_code=502, detail=f"API 错误: HTTP {e.status_code}: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用失败: {e}")
    finally:
        http_client.close()

    urls = extract_image_urls(text)
    if not urls:
        return {"filename": None, "image_b64": None, "text": text, "no_image": True}

    try:
        img_resp = httpx.get(urls[0], timeout=60)
        img_resp.raise_for_status()
        img_b64 = base64.b64encode(img_resp.content).decode()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片下载失败: {e}")

    fname = save_image(img_b64, req.prompt)
    return {"filename": fname, "image_b64": img_b64, "text": text, "no_image": False}


def test_openai_compatible(req: TestRequest) -> dict:
    base_url = normalize_base_url(req.base_url)
    http_client = httpx.Client(timeout=60.0)
    client = OpenAI(api_key=req.api_key, base_url=base_url, http_client=http_client)
    try:
        models = client.models.list()
        model_ids = [m.id for m in models.data]
        image_models = [m for m in model_ids if m in PROVIDERS["openai-compatible"]["models"]]
        return {"ok": True, "message": f"✓ 连接成功，可用图像模型: {', '.join(image_models)}"}
    except APIConnectionError as e:
        return {"ok": False, "message": f"✗ 网络连接失败: {e}"}
    except APIError as e:
        return {"ok": False, "message": f"✗ API 错误: HTTP {e.status_code}: {e.message}"}
    except Exception as e:
        return {"ok": False, "message": f"✗ 连接失败: {e}"}
    finally:
        http_client.close()

# ==================== Provider: OpenAI DALL·E ====================
def generate_openai(req: GenerateRequest) -> dict:
    http_client = httpx.Client(timeout=120.0)
    client = OpenAI(api_key=req.api_key, http_client=http_client)
    try:
        resp = client.images.generate(
            model=req.model,
            prompt=req.prompt,
            size=_map_dalle_size(req.size),
            n=1,
            response_format="b64_json",
        )
        img_b64 = resp.data[0].b64_json
    except APIConnectionError as e:
        raise HTTPException(status_code=502, detail=f"网络连接失败: {e}")
    except APIError as e:
        raise HTTPException(status_code=502, detail=f"API 错误: HTTP {e.status_code}: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用失败: {e}")
    finally:
        http_client.close()

    fname = save_image(img_b64, req.prompt)
    return {"filename": fname, "image_b64": img_b64, "text": "", "no_image": False}


def _map_dalle_size(size: str) -> str:
    """Map our ratio notation to DALL·E supported sizes."""
    ratio = size.split(" ")[0]
    mapping = {
        "1:1": "1024x1024",
        "4:3": "1024x1024",
        "3:4": "1024x1024",
        "16:9": "1792x1024",
        "9:16": "1024x1792",
        "3:2": "1792x1024",
        "2:3": "1024x1792",
        "21:9": "1792x1024",
    }
    return mapping.get(ratio, "1024x1024")


def test_openai(req: TestRequest) -> dict:
    http_client = httpx.Client(timeout=30.0)
    client = OpenAI(api_key=req.api_key, http_client=http_client)
    try:
        models = client.models.list()
        dalle_models = [m.id for m in models.data if m.id.startswith("dall-e")]
        if dalle_models:
            return {"ok": True, "message": f"✓ 连接成功，可用模型: {', '.join(dalle_models)}"}
        return {"ok": True, "message": "✓ 连接成功"}
    except APIConnectionError as e:
        return {"ok": False, "message": f"✗ 网络连接失败: {e}"}
    except APIError as e:
        return {"ok": False, "message": f"✗ API 错误: HTTP {e.status_code}: {e.message}"}
    except Exception as e:
        return {"ok": False, "message": f"✗ 连接失败: {e}"}
    finally:
        http_client.close()

# ==================== Provider: DashScope 百炼 ====================
DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"

def generate_dashscope(req: GenerateRequest) -> dict:
    headers = {
        "Authorization": f"Bearer {req.api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    payload = {
        "model": req.model,
        "input": {"prompt": req.prompt},
        "parameters": {
            "size": _map_dashscope_size(req.size),
            "n": 1,
        },
    }
    if req.image_b64:
        payload["input"]["base_image"] = req.image_b64
        payload["input"]["prompt"] = req.prompt
        # For cosplay model, use different payload structure
        if "cosplay" in req.model:
            payload["model"] = req.model
            payload["input"] = {
                "base_image": req.image_b64,
                "style_image": req.image_b64,
                "prompt": req.prompt,
            }

    try:
        # Submit task
        submit_resp = httpx.post(DASHSCOPE_BASE, json=payload, headers=headers, timeout=30)
        submit_resp.raise_for_status()
        task_data = submit_resp.json()

        if task_data.get("output", {}).get("task_status") == "FAILED":
            raise HTTPException(status_code=500, detail=f"万象任务失败: {task_data.get('output', {}).get('message', '')}")

        task_id = task_data["output"]["task_id"]

        # Poll for result
        for _ in range(60):  # max 2 minutes
            time.sleep(2)
            poll_resp = httpx.get(f"{DASHSCOPE_BASE}/{task_id}", headers=headers, timeout=30)
            poll_resp.raise_for_status()
            result = poll_resp.json()
            status = result.get("output", {}).get("task_status")
            if status == "SUCCEEDED":
                img_url = result["output"]["results"][0]["url"]
                img_resp = httpx.get(img_url, timeout=60)
                img_resp.raise_for_status()
                img_b64 = base64.b64encode(img_resp.content).decode()
                fname = save_image(img_b64, req.prompt)
                return {"filename": fname, "image_b64": img_b64, "text": "", "no_image": False}
            elif status == "FAILED":
                raise HTTPException(status_code=500, detail=f"万象生成失败: {result.get('output', {}).get('message', '')}")

        raise HTTPException(status_code=500, detail="万象任务超时")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"万象调用失败: {e}")


def _map_dashscope_size(size: str) -> str:
    ratio = size.split(" ")[0]
    mapping = {
        "1:1": "1024*1024",
        "4:3": "1024*768",
        "3:4": "768*1024",
        "16:9": "1280*720",
        "9:16": "720*1280",
        "3:2": "1200*800",
        "2:3": "800*1200",
        "21:9": "1680*720",
    }
    return mapping.get(ratio, "1024*1024")


def test_dashscope(req: TestRequest) -> dict:
    headers = {"Authorization": f"Bearer {req.api_key}", "Content-Type": "application/json"}
    try:
        resp = httpx.post(
            DASHSCOPE_BASE,
            json={"model": "wanx2.0-t2i-turbo", "input": {"prompt": "test"}, "parameters": {"size": "1024*1024", "n": 1}},
            headers=headers,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return {"ok": True, "message": "✓ 百炼万象连接成功"}
        return {"ok": False, "message": f"✗ HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"ok": False, "message": f"✗ 连接失败: {e}"}

# ==================== Provider: Stability AI ====================
STABILITY_BASE = "https://api.stability.ai"

def generate_stability(req: GenerateRequest) -> dict:
    headers = {"Authorization": f"Bearer {req.api_key}", "Accept": "application/json"}

    # Build multipart form
    form = {
        "prompt": (None, req.prompt),
        "output_format": (None, "png"),
    }
    if not req.image_b64:
        # text-to-image
        endpoint = f"{STABILITY_BASE}/v2beta/stable-image/generate/sd3"
    else:
        # image-to-image
        endpoint = f"{STABILITY_BASE}/v2beta/stable-image/control/sketch"
        form["image"] = ("image.png", base64.b64decode(req.image_b64), "image/png")

    ratio = req.size.split(" ")[0]
    form["aspect_ratio"] = (None, ratio)

    try:
        resp = httpx.post(endpoint, files=form, headers=headers, timeout=120)
        if resp.status_code == 200:
            img_b64 = base64.b64encode(resp.content).decode()
            fname = save_image(img_b64, req.prompt)
            return {"filename": fname, "image_b64": img_b64, "text": "", "no_image": False}
        else:
            detail = resp.text[:300]
            try:
                detail = resp.json().get("errors", [resp.text])[0]
            except Exception:
                pass
            raise HTTPException(status_code=502, detail=f"Stability 错误: {detail}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stability 调用失败: {e}")


def test_stability(req: TestRequest) -> dict:
    headers = {"Authorization": f"Bearer {req.api_key}"}
    try:
        resp = httpx.get(f"{STABILITY_BASE}/v2beta/account/balance", headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            credits = data.get("credits", "?")
            return {"ok": True, "message": f"✓ Stability 连接成功，剩余额度: {credits}"}
        return {"ok": False, "message": f"✗ HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"ok": False, "message": f"✗ 连接失败: {e}"}

# ==================== Provider dispatch ====================
GENERATORS = {
    "openai-compatible": generate_openai_compatible,
    "openai": generate_openai,
    "dashscope": generate_dashscope,
    "stability": generate_stability,
}

TESTERS = {
    "openai-compatible": test_openai_compatible,
    "openai": test_openai,
    "dashscope": test_dashscope,
    "stability": test_stability,
}

# ==================== API endpoints ====================
@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/api/providers")
def list_providers():
    return PROVIDERS


@app.post("/api/generate")
def generate_image(req: GenerateRequest):
    if not req.api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")
    if req.provider not in GENERATORS:
        raise HTTPException(status_code=400, detail=f"未知 provider: {req.provider}")

    logger.info(f"Generate: provider={req.provider}, model={req.model}, prompt={req.prompt[:40]}...")
    return GENERATORS[req.provider](req)


@app.post("/api/test")
def test_connection(req: TestRequest):
    if not req.api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")
    if req.provider not in TESTERS:
        raise HTTPException(status_code=400, detail=f"未知 provider: {req.provider}")

    logger.info(f"Test: provider={req.provider}")
    return TESTERS[req.provider](req)


@app.get("/api/trending")
def get_trending(seed: str = "", force: str = ""):
    prompts = fetch_online_trending(force=bool(force))
    if seed:
        rng = __import__("random").Random(int(hashlib.md5(seed.encode()).hexdigest(), 16))
        if len(prompts) > 1:
            n = min(12, len(prompts))
            indices = rng.sample(range(len(prompts)), n)
            prompts = [prompts[i] for i in indices]
    source_info = {
        "name": "CivitAI" if _trending_is_online else "本地精选",
        "url": "https://civitai.com/images?sort=Most+Reactions" if _trending_is_online else "",
    }
    return {"date": date.today().isoformat(), "prompts": prompts, "source": source_info}


@app.get("/api/history")
def get_history():
    files = sorted(OUTPUT_DIR.glob("*.png"), key=lambda f: f.stat().st_ctime, reverse=True)
    return [{"filename": f.name, "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_ctime))} for f in files]


@app.get("/api/image/{filename}")
def get_image(filename: str):
    fpath = OUTPUT_DIR / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return {"filename": filename, "image_b64": base64.b64encode(fpath.read_bytes()).decode()}


@app.post("/api/alive")
def keep_alive():
    global _shutdown_timer
    with _shutdown_lock:
        if _shutdown_timer:
            _shutdown_timer.cancel()
            _shutdown_timer = None
    return {"ok": True}


@app.post("/api/shutdown")
def request_shutdown():
    global _shutdown_timer
    def do_shutdown():
        try:
            os.system("taskkill /F /PID %s >nul 2>&1" % os.getppid())
        except Exception:
            pass
        os._exit(0)
    with _shutdown_lock:
        if _shutdown_timer:
            _shutdown_timer.cancel()
        _shutdown_timer = threading.Timer(2.0, do_shutdown)
        _shutdown_timer.start()
    return {"ok": True}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
