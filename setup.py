import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="discord-discard",
    version="0.1.2",
    author="Sanqui",
    author_email="me@sanqui.net",
    description="Tool for medium-scale Discord server archival operations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Sanqui/discard",
    packages=setuptools.find_packages(),
    install_requires=[
        'discord.py==1.6.0',
        'click==7.1.2'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
