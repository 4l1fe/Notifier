from pathlib import Path
from fabric.contrib.project import rsync_project
from fabric.contrib.files import exists
from fabric.api import *


env.use_ssh_config = True

user = 'notify'
home_dir = Path('/home') / user
project_dir = Path('Notify')
deploy_dir = Path('deploy')
env_vars_file = deploy_dir / '.env'
docker_file = deploy_dir / 'Dockerfile'

im_name = cont_name = 'notify'

str_project_dir = str(project_dir)
mapped_addr = '127.0.0.1:8080'
rsync_exclude = '''README
fabfile.py
tests.py
*.log
*.env
.coverage
.gitignore
.git
.idea
.auxilary
__pycache__
htmlcov
*cookie_data*
'''


def check_user(func):
    """Запрещает запускать обертываемые команды во избежание проблем с правами"""

    def wrapper(*args, **kwargs):
        ruser = run('echo $USER')
        if user != ruser:
            abort('Invalid user {}. Must be {}.'.format(ruser, user))

        func(*args, **kwargs)

    return wrapper


@task
def bootstrap():
    with settings(hide('stdout', 'warnings'), warn_only=True):
        # установка необходимых библиотек с ноля
        run('''apt-get update && \
               apt-get install -y linux-image-extra-$(uname -r) linux-image-extra-virtual && \
               apt-get install -y apt-transport-https ca-certificates curl software-properties-common && \
               curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add - &&
               add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" && \
               apt-get update && \
               apt-get install -y docker-ce=17.03.1~ce-0~ubuntu-xenial''')

        # создание пользователя, под которым в дальнейшем происходит работа
        create_host_user()

        # генерация ключей и их настройка, удаление публичного
        generate_ssh_key()


@task
def create_host_user():
    run('''adduser {user} --disabled-password --gecos "" && \
           adduser {user} docker'''.format(user=user))


@task
def generate_ssh_key():
    key_prefix = 'key_tmp'
    ssh_dir = home_dir / '.ssh'
    with cd(str(home_dir),), hide('stdout', 'warnings'):
        run('su {user} -c "mkdir {ssh_dir}"'.format(user=user, ssh_dir=ssh_dir), warn_only=True)
        run('''su {user} -c "ssh-keygen -f {key_prefix} -N '' -q && \
            cat {key_prefix}.pub > {authorized_keys} && \
            chmod 600 {authorized_keys} && \
            chown {user}:{user} {authorized_keys} && \
            rm {key_prefix}.pub" '''.format(user=user, key_prefix=key_prefix, ssh_dir=ssh_dir,
                                            authorized_keys=ssh_dir / 'authorized_keys'))

        # вывод приватного ключа для сохранения и удаление
        priv_key = run('''cat {0} && rm {0}'''.format(key_prefix))
        puts(priv_key)
        puts('ОБЯЗАТЕЛЬНО СОХРАНИТЬ ЭТОТ КЛЮЧ')


@task(name='build')
@check_user
def build(delete=True, ):
    excluded = rsync_exclude.strip().splitlines()
    stop()
    rsync_project(remote_dir=str_project_dir, local_dir='.', exclude=excluded, delete=delete)
    with cd(str_project_dir):
        run('docker build -t {} -f {} .'.format(im_name, docker_file))


@task(name='start')
@check_user
def start(mapped_addr=mapped_addr):
    with cd(str_project_dir):
        run("docker run -d -ti -p {}:8080 --name {} {}".format(mapped_addr, cont_name, im_name))


@task(name='stop')
@check_user
def stop():
    with settings(hide('stdout', 'warnings'), warn_only=True):
        run('docker stop {0} && docker rm {0}'.format(cont_name))


@task
def logs():
    run('docker logs -f {}'.format(cont_name))
