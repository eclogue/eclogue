from eclogue.task import celery
from eclogue.ansible.singTask import SingleTask, only_one
import time

@only_one(key='mytest', timeout=60)
@celery.task()
def add(x, y):
    print('I will sleep')
    time.sleep(20)
    print('I am wake up now')
    return x + y
