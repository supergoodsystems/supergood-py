rm -rf dist
curl -C - -0 https://raw.githubusercontent.com/supergoodsystems/docs/main/integrate-with-clients/python/README.md > README.md
python3 -m build
python3 -m twine upload --repository pypi dist/*
