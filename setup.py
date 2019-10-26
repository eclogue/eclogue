import os
from eclogue import __version__
from setuptools import setup, find_packages

base_dir = os.path.dirname(os.path.dirname(__file__))
requirement_file = os.path.join(base_dir, 'requirements.txt')


def read_file(file_name):
    """Read file and return its contents."""
    with open(file_name, 'r') as f:
        return f.read()


def read_requirements(file_name):
    """Read requirements file as a list."""
    reqs = read_file(file_name).splitlines()
    if not reqs:
        raise RuntimeError(
            "Unable to read requirements from the %s file"
            "That indicates this copy of the source code is incomplete."
            % file_name
        )
    return reqs


setup(
    name='eclogue',
    version=__version__,
    description='ansible web ui',
    long_description='eclogue is a system information web dashboard for ansible and continuous deployment',
    classifiers=[
        'Development Status :: 1 - alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Web',
        'License ::OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: Chinese',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: System :: Systems Administration',
    ],
    keywords='anisble web server',
    author='shiang',
    author_email='mulberry10th@gmail.com',
    url='https://github.com/eclogue/eclogue',
    license='GPLv3+',
    python_requires='>=3.4',
    packages=find_packages(exclude=['tests', '.git', '.vscode', '.idea']),
    include_package_data=True,
    zip_safe=False,
    install_requires=read_requirements(requirement_file),
    test_suite='tests',
    tests_require=['unittest2'],
)
