# -*- coding: utf-8 -*-
import os
import base64
import logging
from flask import Flask, Blueprint, request, jsonify
import ddddocr

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 从环境变量读取 URL 前缀，默认为根目录 /
URL_PREFIX = os.environ.get('URL_PREFIX', '/')

# 创建 Blueprint，设置 URL 前缀
api = Blueprint('api', __name__, url_prefix=URL_PREFIX)


@app.before_request
def log_request():
    """记录每个请求的日志"""
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    logger.info(f"{request.method} {request.path} - {ip}")

# OCR 实例缓存
_ocr_instances = {}


def get_ocr_instance(model_name=None):
    """
    获取 OCR 实例，支持自定义模型
    
    Args:
        model_name: 自定义模型名称（模型文件应放在 /app/models/ 目录下）
                   例如: "custom" 对应 /app/models/custom.onnx 和 /app/models/custom.json
    """
    cache_key = model_name or "default"
    
    if cache_key not in _ocr_instances:
        if model_name:
            model_path = f"/app/models/{model_name}.onnx"
            charset_path = f"/app/models/{model_name}.json"
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型文件不存在: {model_path}")
            
            charsets_path = charset_path if os.path.exists(charset_path) else None
            _ocr_instances[cache_key] = ddddocr.DdddOcr(
                show_ad=False,
                import_onnx_path=model_path,
                charsets_path=charsets_path
            )
        else:
            _ocr_instances[cache_key] = ddddocr.DdddOcr(show_ad=False)
    
    return _ocr_instances[cache_key]


# 滑块检测实例（延迟初始化）
_slider_instance = None


def get_slider_instance():
    global _slider_instance
    if _slider_instance is None:
        _slider_instance = ddddocr.DdddOcr(det=False, ocr=False, show_ad=False)
    return _slider_instance


def _do_ocr(model_name=None):
    """OCR 识别核心逻辑"""
    try:
        if request.is_json:
            data = request.get_json()
            image_b64 = data.get("image")
            
            if not image_b64:
                return jsonify({"success": False, "error": "缺少 image 参数"}), 400
            
            image_bytes = base64.b64decode(image_b64)
        else:
            file = request.files.get("file")
            
            if not file:
                return jsonify({"success": False, "error": "缺少图片文件"}), 400
            
            image_bytes = file.read()
        
        ocr_instance = get_ocr_instance(model_name)
        result = ocr_instance.classification(image_bytes)
        
        return jsonify({
            "success": True,
            "result": result,
            "model": model_name or "default"
        })
        
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/", methods=["GET"])
def index():
    """服务状态检查"""
    return "API运行成功！"


@api.route("/ocr", methods=["POST"])
def ocr():
    """
    OCR 识别接口（使用默认模型）
    
    请求体 JSON: {"image": "base64编码的图片"}
    或上传文件: multipart/form-data, file=图片文件
    """
    return _do_ocr()


@api.route("/model/<model_name>", methods=["POST"])
def ocr_with_model(model_name):
    """
    OCR 识别接口（通过 URL 路径指定自定义模型）
    
    示例: POST /ddddocr/model/dx
    """
    return _do_ocr(model_name)


@api.route("/slide", methods=["POST"])
def slide():
    """
    滑块缺口检测接口
    
    请求体 JSON:
    {
        "target": "目标图片 base64",
        "background": "背景图片 base64"
    }
    """
    try:
        if not request.is_json:
            return jsonify({"success": False, "error": "请使用 JSON 格式"}), 400
        
        data = request.get_json()
        target_b64 = data.get("target")
        bg_b64 = data.get("background")
        
        if not target_b64 or not bg_b64:
            return jsonify({"success": False, "error": "缺少 target 或 background 参数"}), 400
        
        target_bytes = base64.b64decode(target_b64)
        bg_bytes = base64.b64decode(bg_b64)
        
        slider = get_slider_instance()
        result = slider.slide_match(target_bytes, bg_bytes, simple_target=True)
        
        return jsonify({
            "success": True,
            "target": result.get("target", [])
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# 注册 Blueprint
app.register_blueprint(api)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
