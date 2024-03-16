# Use ARGs to set the default version, but allow overrides from the build command
ARG INSTALL_PYTHON_VERSION=3.10   # Update to the latest stable Python version
ARG INSTALL_NODE_VERSION=16       # Update to the latest stable Node.js version

# Node stage
FROM node:${INSTALL_NODE_VERSION}-buster-slim AS node
# Python builder stage
FROM python:${INSTALL_PYTHON_VERSION}-slim-buster AS builder

WORKDIR /app

COPY --from=node /usr/local/bin/ /usr/local/bin/
COPY --from=node /usr/lib/ /usr/lib/
# Workaround for Docker COPY --from bug
RUN true
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY requirements requirements
RUN pip install --no-cache -r requirements/prod.txt

COPY package.json ./
RUN npm install

COPY webpack.config.js autoapp.py ./
COPY alarm_demo alarm_demo
COPY assets assets
COPY .env.example .env
RUN npm run-script build

# Production stage
FROM python:${INSTALL_PYTHON_VERSION}-slim-buster as production

WORKDIR /app

RUN useradd -m sid
RUN chown -R sid:sid /app
USER sid
ENV PATH="/home/sid/.local/bin:${PATH}"

COPY --from=builder --chown=sid:sid /app/alarm_demo/static /app/alarm_demo/static
COPY requirements requirements
RUN pip install --no-cache --user -r requirements/prod.txt

COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY supervisord_programs /etc/supervisor/conf.d

COPY . .

EXPOSE 5000
ENTRYPOINT ["/bin/bash", "shell_scripts/supervisord_entrypoint.sh"]
CMD ["-c", "/etc/supervisor/supervisord.conf"]

# Development stage
FROM builder AS development
RUN pip install --no-cache -r requirements/dev.txt
EXPOSE 2992
EXPOSE 5000
CMD [ "npm", "start" ]
