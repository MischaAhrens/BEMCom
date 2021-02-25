from setuptools import setup

setup(
    name="pyconnector_template",
    version="0.1.2",
    install_requires=["python-dotenv==0.15.*", "paho-mqtt==1.5.*", "pytest"],
    packages=setuptools.find_packages(),
)