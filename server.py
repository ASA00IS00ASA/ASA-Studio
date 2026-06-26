import base64
import logging
import re
import time
import traceback
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI, APIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Image Generator")

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

IMAGE_MODELS = ["nano-banana", "nano-banana-2", "gpt-image-2", "gpt-image-2-vip", "nano-banana-pro"]

# ==================== Daily trending prompts library ====================
TRENDING_PROMPTS = [
    # --- 爆款风格 ---
    {"zh": "潦草涂鸦风：用最笨拙潦草的方式重绘，白色背景，低质糟糕的离谱感", "en": "redraw in the clumsiest, messiest scribble style on white background, ridiculously bad quality, poorly drawn with mouse", "cat": "爆款"},
    {"zh": "3D毛绒应用图标，柔软羊毛质感，柔和工作室灯光，可爱极简风格", "en": "3D fluffy app icon, plush wool texture with visible fibers, soft studio lighting, kawaii minimal style, centered composition", "cat": "爆款"},
    {"zh": "AI小小分身：迷你3D Q版角色站在真实场景中，微缩模型效果", "en": "tiny 3D chibi character standing in a real-world scene, miniature diorama effect, tilt-shift photography", "cat": "爆款"},
    {"zh": "撕纸分层特效：画面被撕开露出底层线稿，多层次混合媒介", "en": "torn paper layered effect revealing line art underneath, mixed media, ripped edge revealing sketch", "cat": "爆款"},
    {"zh": "PS1复古游戏封面，低多边形风格，颗粒感纹理，怀旧游戏包装", "en": "PlayStation 1 retro game cover art, low-poly style, grainy texture, nostalgic game packaging, 1990s aesthetic", "cat": "爆款"},
    {"zh": "珐琅徽章风格，金属珐琅质感，硬朗轮廓，收藏级徽章设计", "en": "enamel pin design style, metallic enamel texture, hard enamel finish, collectible pin, glossy raised metal edges", "cat": "爆款"},

    # --- 电影感 ---
    {"zh": "赛博朋克都市夜景，霓虹灯倒映在湿漉漉的街道，35mm胶片质感", "en": "cyberpunk city at night, neon reflections on wet pavement, shot on 35mm film, Blade Runner aesthetic, cinematic", "cat": "电影感"},
    {"zh": "电影级肖像，伦勃朗布光，大光圈浅景深，柯达胶片调色", "en": "cinematic portrait, Rembrandt lighting, wide aperture shallow depth of field, Kodak Portra 400 color grading", "cat": "电影感"},
    {"zh": "黄金时刻的草原奔跑，体积雾，逆光剪影，电影画幅2.35:1", "en": "running through grassland at golden hour, volumetric fog, backlit silhouette, anamorphic 2.35:1, cinematic", "cat": "电影感"},
    {"zh": "雨中东京街头，霓虹招牌倒影，透明雨伞，胶片颗粒感", "en": "rainy Tokyo street at night, neon sign reflections, transparent umbrellas, film grain, cinematic mood", "cat": "电影感"},

    # --- 设计 & 品牌 ---
    {"zh": "极简品牌Logo设计，几何抽象，2-3色搭配，干净线条可缩放矢量", "en": "minimalist logo design, geometric abstract, 2-3 color palette, clean lines, scalable vector style, professional", "cat": "设计"},
    {"zh": "精品咖啡包装设计，哑光黑色袋子，铜箔烫印，现代工匠美学", "en": "premium coffee bag packaging, matte black pouch, copper foil stamping, modern artisan aesthetic, product photography", "cat": "设计"},
    {"zh": "App Store截图背景，光滑渐变，玻璃拟态，冷静蓝白调，大量留白", "en": "App Store screenshot background, smooth gradients, glassmorphism shapes, calm blue and white palette, plenty of negative space", "cat": "设计"},
    {"zh": "现代品牌情绪板，柔和中性色，温暖晨光，极简室内，天然纹理", "en": "moodboard for modern wellness brand, soft neutral colors, warm morning light, minimalist interiors, natural textures, editorial design", "cat": "设计"},

    # --- 摄影 ---
    {"zh": "专业美食摄影，俯拍角度，自然日光，浅景深，美食杂志质感", "en": "professional food photography, overhead flat lay, natural daylight, shallow depth of field, food magazine quality", "cat": "摄影"},
    {"zh": "商业产品摄影，大理石表面，柔光棚拍，超写实，8K分辨率", "en": "commercial product photography on marble surface, soft diffused studio lighting, hyperrealistic, 8K resolution", "cat": "摄影"},
    {"zh": "航拍自然风光，鸟瞰视角，清晨薄雾，阳光穿过云层，国家地理风格", "en": "aerial nature landscape, bird's eye view, morning mist, sun rays through clouds, National Geographic style", "cat": "摄影"},
    {"zh": "微距昆虫摄影，露珠细节，焦外散景，100mm微距镜头", "en": "macro insect photography, dewdrop details, creamy bokeh, 100mm macro lens, extreme detail", "cat": "摄影"},

    # --- 插画 & 艺术 ---
    {"zh": "宫崎骏风格动画场景，温暖色调，手绘质感，梦幻天空之城", "en": "Studio Ghibli style animated scene, warm color palette, hand-painted texture, dreamy floating castle, Makoto Shinkai lighting", "cat": "插画"},
    {"zh": "水墨画风格山水，大面积留白，干笔飞白，诗意意境", "en": "ink wash painting landscape, large negative space, dry brush texture, poetic atmosphere, traditional Chinese sumi-e style", "cat": "插画"},
    {"zh": "浮世绘风格海浪，葛饰北斋灵感，木板印刷质感，靛蓝色调", "en": "ukiyo-e style ocean wave, Hokusai inspired, woodblock print texture, indigo blue tones, Japanese art", "cat": "插画"},
    {"zh": "蒸汽波美学，CRT显示器光晕，VHS噪点，粉紫渐变，80年代字体", "en": "vaporwave aesthetic, CRT monitor glow, VHS noise, pink and purple gradient, 1980s typography, retro synthwave", "cat": "插画"},

    # --- 3D & 数字艺术 ---
    {"zh": "3D玻璃材质抽象雕塑，次表面散射，柔光工作室环境，8K渲染", "en": "3D glass abstract sculpture, subsurface scattering, soft studio lighting, Octane render, 8K, iridescent", "cat": "3D"},
    {"zh": "低多边形等距房间，柔和配色，游戏资产风格，Blender渲染", "en": "low poly isometric room, pastel color palette, game asset style, cozy vibes, Blender render, diorama", "cat": "3D"},
    {"zh": "数字花卉超现实景观，柔和雾化失焦，浪漫粉彩调色板", "en": "digital surreal botanical landscape, soft hazy out-of-focus, romantic pastel palette, dreamlike garden", "cat": "3D"},
    {"zh": "迷幻超现实混合纹理，2D与3D层叠深度，光学错觉，柔和霓虹", "en": "psychedelic surrealism, mixed 2D and 3D textures, layered depth, optical illusions, soft neon tones", "cat": "3D"},

    # --- 时尚 & 人物 ---
    {"zh": "高级时装编辑摄影，模特穿着前卫设计，戏剧性光影，杂志质感", "en": "haute couture editorial photo, avant-garde fashion, dramatic lighting, magazine quality, high fashion photography", "cat": "时尚"},
    {"zh": "老钱风暗黑女性气场，和服改良版，Quiet Luxury，低调奢华", "en": "quiet luxury dark feminine aesthetic, modern kimono, old money style, understated elegance, matte painting", "cat": "时尚"},
    {"zh": "日系清新写真，自然光，胶片色调，少女感，夏日氛围", "en": "Japanese fresh style portrait, natural lighting, film tone color grading, summer vibes, youth photography", "cat": "时尚"},

    # --- 建筑 & 室内 ---
    {"zh": "现代极简主义建筑外观，大面积玻璃幕墙，黄金时刻光影，建筑摄影", "en": "modern minimalist architecture exterior, large glass curtain wall, golden hour lighting, architectural photography", "cat": "建筑"},
    {"zh": "侘寂风格室内设计，天然材料，柔和光线，平静氛围，绿植点缀", "en": "wabi-sabi interior design, natural materials, soft diffused light, calm atmosphere, indoor plants, serene", "cat": "建筑"},

    # --- 奇幻 & 科幻 ---
    {"zh": "史诗级奇幻场景，漂浮岛屿，瀑布倾泻入云海，魔法光效，壮观", "en": "epic fantasy landscape, floating islands, waterfalls cascading into clouds, magical glow, breathtaking, matte painting", "cat": "奇幻"},
    {"zh": "怀旧未来主义，液态金属，全息箔，像素艺术，酸性色彩，Y2K复兴", "en": "retro-futurism, liquid metal surfaces, holographic foil, pixel art elements, acid colors, Y2K revival aesthetic", "cat": "奇幻"},
    {"zh": "科幻太空站内部，巨大观景窗俯瞰星云，极简工业设计，电影级光照", "en": "sci-fi space station interior, massive viewing window overlooking nebula, minimalist industrial design, cinematic lighting", "cat": "奇幻"},

    # --- 可爱 & 治愈 ---
    {"zh": "可爱柴犬戴着毛线帽，柔和粉彩背景，3D毛绒质感，治愈系", "en": "cute Shiba Inu wearing knitted beanie, soft pastel background, 3D fluffy texture, kawaii, healing vibes", "cat": "治愈"},
    {"zh": "猫咪咖啡馆水彩插画，温暖舒适氛围，手绘线条，淡雅配色", "en": "cat cafe watercolor illustration, warm cozy atmosphere, hand-drawn lines, light elegant color palette, whimsical", "cat": "治愈"},
    {"zh": "宫崎骏风格森林小屋，苔藓覆盖的屋顶，炊烟袅袅，萤火虫飞舞", "en": "Ghibli style forest cottage, moss-covered roof, chimney smoke, fireflies glowing at dusk, magical cozy", "cat": "治愈"},
]

import hashlib
from datetime import date

def get_daily_trending() -> list[dict]:
    """Return 8 prompts rotated daily based on date."""
    today = date.today().isoformat()
    seed = int(hashlib.md5(today.encode()).hexdigest(), 16)
    rng = __import__("random").Random(seed)
    indices = rng.sample(range(len(TRENDING_PROMPTS)), min(12, len(TRENDING_PROMPTS)))
    return [TRENDING_PROMPTS[i] for i in indices]


class GenerateRequest(BaseModel):
    prompt: str
    size: str = "1024x1024"
    model: str = "nano-banana"
    api_key: str
    base_url: str
    image_b64: str | None = None  # optional reference image for img2img


class TestRequest(BaseModel):
    api_key: str
    base_url: str


# 全局异常处理，确保始终返回 JSON
@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {traceback.format_exc()}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


def normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


def extract_image_urls(text: str) -> list[str]:
    urls = []
    urls.extend(re.findall(r"!\[.*?\]\((https?://[^\s)]+)\)", text))
    urls.extend(re.findall(r"(https?://[^\s]+\.(?:png|jpg|jpeg|gif|webp))", text, re.I))
    return urls


@app.post("/api/generate")
def generate_image(req: GenerateRequest):
    if not req.api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")

    base_url = normalize_base_url(req.base_url)
    logger.info(f"Generate: base_url={base_url}, model={req.model}, prompt={req.prompt[:40]}...")

    http_client = httpx.Client(timeout=120.0)
    client = OpenAI(api_key=req.api_key, base_url=base_url, http_client=http_client)

    # Build message content: text-only or multimodal (text + image)
    if req.image_b64:
        content_parts = [
            {"type": "text", "text": req.prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{req.image_b64}"}},
        ]
        messages = [{"role": "user", "content": content_parts}]
        logger.info(f"Generate (img2img): model={req.model}, prompt={req.prompt[:40]}..., image_len={len(req.image_b64)}")
    else:
        messages = [{"role": "user", "content": req.prompt}]
        logger.info(f"Generate: model={req.model}, prompt={req.prompt[:40]}...")

    try:
        resp = client.chat.completions.create(
            model=req.model,
            messages=messages,
            max_tokens=2000,
        )
        content = resp.choices[0].message.content or ""
        logger.info(f"Chat response: {content[:200]}")
    except APIError as e:
        raise HTTPException(status_code=502, detail=f"API 错误: HTTP {e.status_code}: {e.message}")
    except Exception as e:
        logger.error(f"Chat call failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"调用失败: {e}")

    urls = extract_image_urls(content)
    if not urls:
        return {"filename": None, "image_b64": None, "text": content, "no_image": True}

    # Download the image
    try:
        img_resp = http_client.get(urls[0], timeout=60)
        img_resp.raise_for_status()
        img_b64 = base64.b64encode(img_resp.content).decode()
    except Exception as e:
        logger.error(f"Image download failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"图片下载失败: {e}")
    finally:
        http_client.close()

    ts = int(time.time())
    safe_name = re.sub(r"[\s\\/:*?\"<>|]", "_", req.prompt)
    safe_name = re.sub(r"[^\w一-鿿_-]", "", safe_name)
    safe_name = safe_name[:50]
    fname = f"{ts}_{safe_name}.png"
    (OUTPUT_DIR / fname).write_bytes(base64.b64decode(img_b64))

    return {"filename": fname, "image_b64": img_b64, "text": content, "no_image": False}


@app.post("/api/test")
def test_connection(req: TestRequest):
    if not req.api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key")

    base_url = normalize_base_url(req.base_url)
    logger.info(f"Test: base_url={base_url}")

    http_client = httpx.Client(timeout=60.0)
    client = OpenAI(api_key=req.api_key, base_url=base_url, http_client=http_client)

    try:
        models = client.models.list()
        model_ids = [m.id for m in models.data]
        image_models = [m for m in model_ids if m in IMAGE_MODELS]
        http_client.close()
        return {"ok": True, "message": f"✓ 连接成功，可用图像模型: {', '.join(image_models)}"}
    except APIError as e:
        http_client.close()
        return {"ok": False, "message": f"✗ API 错误: HTTP {e.status_code}: {e.message}"}
    except Exception as e:
        http_client.close()
        logger.error(f"Test failed: {traceback.format_exc()}")
        return {"ok": False, "message": f"✗ 连接失败: {e}"}


@app.get("/api/trending")
def get_trending():
    """Return today's trending prompts."""
    return {"date": date.today().isoformat(), "prompts": get_daily_trending()}


@app.get("/api/history")
def get_history():
    files = sorted(OUTPUT_DIR.glob("*.png"), key=lambda f: f.stat().st_ctime, reverse=True)
    return [
        {
            "filename": f.name,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_ctime)),
        }
        for f in files
    ]


@app.get("/api/image/{filename}")
def get_image(filename: str):
    fpath = OUTPUT_DIR / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    b64 = base64.b64encode(fpath.read_bytes()).decode()
    return {"filename": filename, "image_b64": b64}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
