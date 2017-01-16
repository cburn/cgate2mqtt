from setuptools import find_packages, setup
setup(name="cgate2mqtt",
      version="0.1.0",
      description="Clipsal C-Gate to MQTT bridge",
      author="Chris Burn",
      author_email='chrisburn@fastmail.net',
      platforms=["any"],
      packages=find_packages(),

      install_requires = ['txcgate', 'Twisted', 'twisted-mqtt'],
)
