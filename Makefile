
PY?=python3
PIP?=pip3
APP=app.main:app
PORT?=8000

.PHONY: venv install dev run test-client clean

venv:
	$(PY) -m venv .venv
	. .venv/bin/activate && $(PIP) install --upgrade pip
	. .venv/bin/activate && $(PIP) install -r requirements.txt

install:
	. .venv/bin/activate && pip install -r requirements.txt

dev:
	ELEVENLABS_API_KEY=$${ELEVENLABS_API_KEY} . .venv/bin/activate && uvicorn $(APP) --reload --host 0.0.0.0 --port $(PORT)

run:
	. .venv/bin/activate && uvicorn $(APP) --host 0.0.0.0 --port $(PORT)

test-client:
	. .venv/bin/activate && $(PY) scripts/test_client.py --text "$${TEXT:-Hej världen! Det här är ett test.}" --url "$${URL:-ws://localhost:8000/ws/tts}" --out "$${OUT:-out.wav}" --voice "$${VOICE_ID:-}"

clean:
	rm -rf .venv __pycache__ **/__pycache__ *.pyc .pytest_cache
