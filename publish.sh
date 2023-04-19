source .env

# Clean existing builds
rm -rf dist

# Pull latest README.md from Gitbook
curl -C - -0 https://raw.githubusercontent.com/supergoodsystems/docs/main/integrate-with-clients/python/README.md > README.md
git add README.md
git commit -m "Update README.md"

# Bump version, default patch
bump2version patch

# Build and publish
python3 -m build
python3 -m twine upload -u __token__ -p $PYPI_TOKEN $ --repository pypi dist/*
