import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='supergood',
    version='1.0.11',
    author='Alex Klarfeld',
    description='The Python client for Supergood',
    long_description=long_description,
    long_description_content_type='text/markdown',
    package=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    py_modules=['supergood'],
    package_dir={'': 'src'},
    install_requires=[
        'python-dotenv==1.0.0',
        'jsonpickle',
        'urllib3==1.26',
        'requests==2.28.0',
        'aiohttp==3.8.4',
        'pydash==7.0.1',
    ],
    extras_require={
        'test': [
            'requests==2.28.0',
            'urllib3==1.26',
            'pytest==7.2.1',
            'pytest_httpserver==1.0.6',
            'python-dotenv==1.0.0',
            'Werkzeug',
            'jsonpickle==3.0.1',
            'pytest-mock==3.10.0'
        ]
    },
)
