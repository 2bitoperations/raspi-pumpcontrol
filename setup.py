from setuptools import setup
import os

version = "0.0.1"

homedir = "/root/raspi-pumpcontrol/"

if os.path.isfile("/etc/raspipump.conf"):
    cmd = "cp -u " "/etc/raspipump.conf " + "/etc/raspisump.conf.save"
    os.system(cmd)

raspi_pump_files = [
    "bin/pump-control.py",
]

add_files = [
    ("/etc/raspipump.example.conf", ["raspipump.example.conf"]),
]

setup(
    name="raspipump",
    version=version,
    description="A well pump control system for Raspberry Pi",
    long_description_content_type="text/markdown",
    long_description=open("./README.md", "r").read(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Natural Language :: English",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.7",
        "Topic :: Home Automation",
        "License :: OSI Approved :: MIT License",
    ],
    author="Andrew Malota",
    author_email="2bitoperations@gmail.com",
    url="https://github.com/2bitoperations/raspi-pumpcontrol",
    download_url="https://github.com/2bitoperations/raspi-pumpcontrol",
    license="Creative Commons Zero v1.0 Universal",
    packages=["raspipump"],
    scripts=raspi_pump_files,
    data_files=add_files,
    install_requires=["python3-gpiozero", "ISStreamer", "requests"],
)

if os.path.isdir(homedir):
    cmd = "chown -R root " + homedir
    os.system(cmd)
    cmd = "chmod 600 " + homedir + "raspipump.conf"
    os.system(cmd)

