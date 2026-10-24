import base64
import importlib.util
import os
import threading
import time


class VisionError(RuntimeError):
    pass


class VisionService:
    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.Lock()
        self._ocr = None

    def status(self):
        return {"opencv": importlib.util.find_spec("cv2") is not None,
                "paddleocr": importlib.util.find_spec("paddleocr") is not None,
                "loaded": self._ocr is not None,
                "message": "OCR 首次使用时加载；摄像头需在目标硬件核验"}

    def _dependencies(self):
        try:
            import cv2
            import numpy as np
            return cv2, np
        except ImportError as exc:
            raise VisionError("尚未安装图像依赖，请按部署文档安装 OpenCV 和 NumPy") from exc

    def _recognize(self, frame):
        if self._ocr is None:
            os.environ.setdefault("PADDLE_PDX_CPU_NUM_THREADS", str(self.settings.ocr_threads))
            try:
                from paddleocr import PaddleOCR
                self._ocr = PaddleOCR(device="cpu", cpu_threads=self.settings.ocr_threads,
                    text_detection_model_name=self.settings.ocr_det,
                    text_recognition_model_name=self.settings.ocr_rec,
                    use_doc_orientation_classify=False, use_doc_unwarping=False,
                    use_textline_orientation=False)
            except ImportError as exc:
                raise VisionError("尚未安装 PaddleOCR；文字输入功能仍可使用") from exc
        # PaddleOCR's image-array input follows OpenCV's BGR convention.
        results = self._ocr.predict(frame)
        lines = []
        for result in results:
            texts = result.get("rec_texts", [])
            scores = result.get("rec_scores", [])
            for i, text in enumerate(texts):
                lines.append({"text": str(text),
                              "confidence": float(scores[i]) if i < len(scores) else None})
        return lines

    def process(self, image=None):
        if not self.lock.acquire(blocking=False):
            raise VisionError("图片识别正在进行，请稍候再试")
        try:
            cv2, np = self._dependencies()
            start = time.monotonic()
            capture_seconds = None
            if image is not None:
                frame = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    raise VisionError("无法解码图片，请使用 PNG 或 JPEG")
            else:
                capture = cv2.VideoCapture(self.settings.camera_device, cv2.CAP_V4L2)
                try:
                    if not capture.isOpened():
                        raise VisionError("摄像头无法打开，请核对 CAMERA_DEVICE 和设备权限")
                    frame = None
                    for _ in range(self.settings.camera_warmup + 1):
                        ok, frame = capture.read()
                        if not ok:
                            raise VisionError("摄像头读取失败")
                        if self.settings.camera_warmup:
                            time.sleep(0.05)
                finally:
                    capture.release()
                capture_seconds = round(time.monotonic() - start, 3)
            if frame.shape[0] * frame.shape[1] > 24_000_000:
                raise VisionError("图片过大，请先缩小到 2400 万像素以内")
            height, width = frame.shape[:2]
            scale = min(1, 2000 / max(height, width))
            if scale < 1:
                frame = cv2.resize(frame, (int(width * scale), int(height * scale)))
            ocr_start = time.monotonic()
            lines = self._recognize(frame)
            ocr_seconds = round(time.monotonic() - ocr_start, 3)
            ok, preview = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            return {"text": "\n".join(x["text"] for x in lines), "lines": lines,
                    "preview": "data:image/jpeg;base64," + base64.b64encode(preview).decode() if ok else None,
                    "metrics": {"capture_seconds": capture_seconds, "ocr_seconds": ocr_seconds,
                                "total_seconds": round(time.monotonic() - start, 3),
                                "includes_initialization": True}}
        except VisionError:
            raise
        except Exception as exc:
            raise VisionError("图像识别失败，请检查模型缓存、依赖版本和本地日志") from exc
        finally:
            self.lock.release()
