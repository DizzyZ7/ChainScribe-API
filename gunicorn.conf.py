import multiprocessing
import os


bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_CONCURRENCY", str(min(multiprocessing.cpu_count() * 2 + 1, 8))))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
accesslog = None
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
capture_output = True
worker_tmp_dir = "/dev/shm"
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")
