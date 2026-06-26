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
    {"zh": "潦草涂鸦风：用最笨拙潦草的方式重绘，白色背景，低质糟糕的离谱感", "en": "redraw in the clumsiest, messiest scribble style on white background, ridiculously bad quality", "cat": "爆款"},
    {"zh": "3D毛绒应用图标，柔软羊毛质感，柔和工作室灯光，可爱极简风格", "en": "3D fluffy app icon, plush wool texture with visible fibers, soft studio lighting, kawaii minimal style", "cat": "爆款"},
    {"zh": "AI小小分身：迷你3D Q版角色站在真实场景中，微缩模型效果", "en": "tiny 3D chibi character standing in a real-world scene, miniature diorama effect, tilt-shift photography", "cat": "爆款"},
    {"zh": "撕纸分层特效：画面被撕开露出底层线稿，多层次混合媒介", "en": "torn paper layered effect revealing line art underneath, mixed media, ripped edge revealing sketch", "cat": "爆款"},
    {"zh": "PS1复古游戏封面，低多边形风格，颗粒感纹理，怀旧游戏包装", "en": "PlayStation 1 retro game cover art, low-poly style, grainy texture, nostalgic game packaging", "cat": "爆款"},
    {"zh": "珐琅徽章风格，金属珐琅质感，硬朗轮廓，收藏级徽章设计", "en": "enamel pin design style, metallic enamel texture, hard enamel finish, collectible pin", "cat": "爆款"},
    {"zh": "赛博朋克都市夜景，霓虹灯倒映在湿漉漉的街道，35mm胶片质感", "en": "cyberpunk city at night, neon reflections on wet pavement, shot on 35mm film, Blade Runner aesthetic", "cat": "电影感"},
    {"zh": "电影级肖像，伦勃朗布光，大光圈浅景深，柯达胶片调色", "en": "cinematic portrait, Rembrandt lighting, wide aperture shallow depth of field, Kodak Portra 400 color grading", "cat": "电影感"},
    {"zh": "黄金时刻的草原奔跑，体积雾，逆光剪影，电影画幅2.35:1", "en": "running through grassland at golden hour, volumetric fog, backlit silhouette, anamorphic 2.35:1", "cat": "电影感"},
    {"zh": "雨中东京街头，霓虹招牌倒影，透明雨伞，胶片颗粒感", "en": "rainy Tokyo street at night, neon sign reflections, transparent umbrellas, film grain, cinematic mood", "cat": "电影感"},
    {"zh": "极简品牌Logo设计，几何抽象，2-3色搭配，干净线条可缩放矢量", "en": "minimalist logo design, geometric abstract, 2-3 color palette, clean lines, scalable vector style", "cat": "设计"},
    {"zh": "精品咖啡包装设计，哑光黑色袋子，铜箔烫印，现代工匠美学", "en": "premium coffee bag packaging, matte black pouch, copper foil stamping, modern artisan aesthetic", "cat": "设计"},
    {"zh": "App Store截图背景，光滑渐变，玻璃拟态，冷静蓝白调，大量留白", "en": "App Store screenshot background, smooth gradients, glassmorphism shapes, calm blue and white palette", "cat": "设计"},
    {"zh": "现代品牌情绪板，柔和中性色，温暖晨光，极简室内，天然纹理", "en": "moodboard for modern wellness brand, soft neutral colors, warm morning light, minimalist interiors", "cat": "设计"},
    {"zh": "专业美食摄影，俯拍角度，自然日光，浅景深，美食杂志质感", "en": "professional food photography, overhead flat lay, natural daylight, shallow depth of field, food magazine quality", "cat": "摄影"},
    {"zh": "商业产品摄影，大理石表面，柔光棚拍，超写实，8K分辨率", "en": "commercial product photography on marble surface, soft diffused studio lighting, hyperrealistic, 8K resolution", "cat": "摄影"},
    {"zh": "航拍自然风光，鸟瞰视角，清晨薄雾，阳光穿过云层，国家地理风格", "en": "aerial nature landscape, bird's eye view, morning mist, sun rays through clouds, National Geographic style", "cat": "摄影"},
    {"zh": "微距昆虫摄影，露珠细节，焦外散景，100mm微距镜头", "en": "macro insect photography, dewdrop details, creamy bokeh, 100mm macro lens, extreme detail", "cat": "摄影"},
    {"zh": "宫崎骏风格动画场景，温暖色调，手绘质感，梦幻天空之城", "en": "Studio Ghibli style animated scene, warm color palette, hand-painted texture, dreamy floating castle", "cat": "插画"},
    {"zh": "水墨画风格山水，大面积留白，干笔飞白，诗意意境", "en": "ink wash painting landscape, large negative space, dry brush texture, poetic atmosphere, Chinese sumi-e style", "cat": "插画"},
    {"zh": "浮世绘风格海浪，葛饰北斋灵感，木板印刷质感，靛蓝色调", "en": "ukiyo-e style ocean wave, Hokusai inspired, woodblock print texture, indigo blue tones", "cat": "插画"},
    {"zh": "蒸汽波美学，CRT显示器光晕，VHS噪点，粉紫渐变，80年代字体", "en": "vaporwave aesthetic, CRT monitor glow, VHS noise, pink and purple gradient, 1980s typography", "cat": "插画"},
    {"zh": "3D玻璃材质抽象雕塑，次表面散射，柔光工作室环境，8K渲染", "en": "3D glass abstract sculpture, subsurface scattering, soft studio lighting, Octane render, 8K", "cat": "3D"},
    {"zh": "低多边形等距房间，柔和配色，游戏资产风格，Blender渲染", "en": "low poly isometric room, pastel color palette, game asset style, cozy vibes, Blender render", "cat": "3D"},
    {"zh": "数字花卉超现实景观，柔和雾化失焦，浪漫粉彩调色板", "en": "digital surreal botanical landscape, soft hazy out-of-focus, romantic pastel palette, dreamlike garden", "cat": "3D"},
    {"zh": "迷幻超现实混合纹理，2D与3D层叠深度，光学错觉，柔和霓虹", "en": "psychedelic surrealism, mixed 2D and 3D textures, layered depth, optical illusions, soft neon tones", "cat": "3D"},
    {"zh": "高级时装编辑摄影，模特穿着前卫设计，戏剧性光影，杂志质感", "en": "haute couture editorial photo, avant-garde fashion, dramatic lighting, magazine quality", "cat": "时尚"},
    {"zh": "老钱风暗黑女性气场，和服改良版，Quiet Luxury，低调奢华", "en": "quiet luxury dark feminine aesthetic, modern kimono, old money style, understated elegance", "cat": "时尚"},
    {"zh": "日系清新写真，自然光，胶片色调，少女感，夏日氛围", "en": "Japanese fresh style portrait, natural lighting, film tone color grading, summer vibes", "cat": "时尚"},
    {"zh": "现代极简主义建筑外观，大面积玻璃幕墙，黄金时刻光影", "en": "modern minimalist architecture exterior, large glass curtain wall, golden hour lighting, architectural photography", "cat": "建筑"},
    {"zh": "侘寂风格室内设计，天然材料，柔和光线，平静氛围，绿植点缀", "en": "wabi-sabi interior design, natural materials, soft diffused light, calm atmosphere, indoor plants", "cat": "建筑"},
    {"zh": "史诗级奇幻场景，漂浮岛屿，瀑布倾泻入云海，魔法光效，壮观", "en": "epic fantasy landscape, floating islands, waterfalls cascading into clouds, magical glow, breathtaking", "cat": "奇幻"},
    {"zh": "怀旧未来主义，液态金属，全息箔，像素艺术，酸性色彩，Y2K复兴", "en": "retro-futurism, liquid metal surfaces, holographic foil, pixel art elements, acid colors, Y2K revival", "cat": "奇幻"},
    {"zh": "科幻太空站内部，巨大观景窗俯瞰星云，极简工业设计，电影级光照", "en": "sci-fi space station interior, massive viewing window overlooking nebula, cinematic lighting", "cat": "奇幻"},
    {"zh": "可爱柴犬戴着毛线帽，柔和粉彩背景，3D毛绒质感，治愈系", "en": "cute Shiba Inu wearing knitted beanie, soft pastel background, 3D fluffy texture, kawaii", "cat": "治愈"},
    {"zh": "猫咪咖啡馆水彩插画，温暖舒适氛围，手绘线条，淡雅配色", "en": "cat cafe watercolor illustration, warm cozy atmosphere, hand-drawn lines, light elegant color palette", "cat": "治愈"},
]

def get_daily_trending() -> list[dict]:
    today_str = date.today().isoformat()
    seed = int(hashlib.md5(today_str.encode()).hexdigest(), 16)
    rng = __import__("random").Random(seed)
    indices = rng.sample(range(len(TRENDING_PROMPTS)), min(12, len(TRENDING_PROMPTS)))
    return [TRENDING_PROMPTS[i] for i in indices]

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
def get_trending():
    return {"date": date.today().isoformat(), "prompts": get_daily_trending()}


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
