import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="supergood",
    version="1.1.3",
    author="Alex Klarfeld",
    description="The Python client for Supergood",
    long_description=long_description,
    long_description_content_type="text/markdown",
    package=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    py_modules=["supergood"],
    package_dir={"": "src"},
    install_requires=[
        "aiohttp",
        "httpx",
        "jsonpickle",
        "pydash==7.0.1",
        "python-dotenv==1.0.0",
        "requests",
        "tldextract>=5",
        "urllib3>=1.26,<2.0",
    ],
    extras_require={
        "test": [
            "requests",
            "urllib3>=1.26,<2.0",
            "pytest==7.2.1",
            "pytest_httpserver==1.0.8",
            "python-dotenv==1.0.0",
            "Werkzeug",
            "jsonpickle==3.0.1",
            "pytest-mock==3.10.0",
        ]
    },
)
