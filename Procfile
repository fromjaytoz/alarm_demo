release: flask db upgrade
web: gunicorn alarm_demo.app:create_app\(\) -b 0.0.0.0:$PORT -w 3
