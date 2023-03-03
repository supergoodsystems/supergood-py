import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='supergood',
    version='1.0.0',
    author='Alex Klarfeld',
    description='A Python client for Supergood',
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
        'pydash',
        'python-dotenv',
        'requests'
    ]
)
