FROM astral/uv:python3.14-bookworm-slim

RUN apt-get update
RUN apt-get install git -y


WORKDIR /app
COPY pyproject.toml uv.lock ./


RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
RUN --mount=type=ssh uv sync --frozen

COPY . . 

EXPOSE 8000
CMD ["uv", "run", "main.py"]