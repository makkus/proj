from setuptools import setup

setup(name='pyroji',
      version='0.2',
      author="Markus Binsteiner",
      author_email="makkus@gmail.com",
      install_requires=[
          "argparse",
          "requests",
          "psutil"
      ],
      packages=["pyroji"],
      entry_points={
          'console_scripts': [
              'pyroji = pyroji.pyroji:run'
          ],
      },
      description="Project management helper"
)
