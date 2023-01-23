PROJECT=my_package

install:
	curl -sSL https://install.python-poetry.org | python3 -
	poetry install

win-install:
	powershell "(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python"
	poetry install

install-packages:
	poetry install

lock:
	poetry lock

dev:
	poetry run flet -r -d main.py

run:
	poetry run flet main.py

requirements:
	poetry export -f requirements.txt --output requirements.txt --without-hashes
