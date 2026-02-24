FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# 车辆指令签名代理（镜像内路径 /app/http_proxy/；仓库内可能为 macOS 版，容器内运行需 Linux 版）
RUN chmod +x /app/http_proxy/tesla-http-proxy 2>/dev/null || true

EXPOSE 8080

CMD ["python", "tesla_oauth_demo.py"]
