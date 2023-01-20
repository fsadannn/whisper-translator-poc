PROJECT=my_package

.PHONY: install
install:
	curl -sSL https://install.python-poetry.org | python3 -
	# for windows comment the line above and uncomment the next line, for powershell only the next line
	# powershell "(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | | python"
	poetry install

.PHONY: install-packages
install-packages:
	poetry install

.PHONY: lock
lock:
	poetry lock



