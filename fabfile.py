from pathlib import Path
from fabric.api import *
from run import NOTIFY_PORT


env.use_ssh_config = True

user = 'notify'
home_dir = Path('/home') / user
deploy_dir = Path('deploy')
docker_file = deploy_dir / 'Dockerfile'
cont_name = 'notify'
im_name = 'registry/' + cont_name
mapped_addr = '127.0.0.1:8080'


def check_user(func):
    """Запрещает запускать обертываемые команды во избежание проблем с правами"""

    def wrapper(*args, **kwargs):
        ruser = run('echo $USER')
        if user != ruser:
            abort('Invalid user {}. Must be {}.'.format(ruser, user))

        func(*args, **kwargs)

    return wrapper


def _make_full_img_name(tag):
    tag = im_name + ':' + tag if tag else im_name
    return tag


def _check_doker_hub_login(remote=False):
    with hide('output', 'running'):
        if remote:
            info = run('docker info')
        else:
            info = local('docker info', capture=True)
    if not 'Username' in info:
        abort('НЕОБХОДИМО АВТОРИЗОВАТЬСЯ В ДОКЕР ХАБЕ')

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


@task
def build(tag=None):
    img_name = _make_full_img_name(tag)
    local('docker build -t {} -f {} .'.format(img_name, docker_file))
    return img_name


@task
def push(tag=None):
    _check_doker_hub_login()
    tag = build(tag)
    local('docker push {}'.format(tag))


@task(name='start')
@check_user
def start(mapped_addr=mapped_addr, tag=None):
    _check_doker_hub_login(remote=True)
    img_name = _make_full_img_name(tag)
    stop()
    run('docker pull {}'.format(img_name))
    run("docker run -d -ti -p {}:{} --name {} --restart=always {}"
        .format(mapped_addr, NOTIFY_PORT, cont_name, img_name))


@task(name='stop')
@check_user
def stop():
    with settings(hide('stdout', 'warnings'), warn_only=True):
        run('docker stop {0} && docker rm {0}'.format(cont_name))


@task
def logs():
    run('docker logs -f {}'.format(cont_name))
