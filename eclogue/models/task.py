import time
import datetime
from eclogue.model import Model


class Task(Model):
    name = 'tasks'

    def histogram(self, days=15):
        hour = 3600
        histogram = self.collection.aggregate([
            {
                '$match': {
                    'created_at': {
                        '$gte': time.time() - 24 * hour * days,
                        '$lte': time.time()
                    },
                }
            },
            {
                '$group': {
                    '_id': {
                        'interval': {
                            '$subtract': [
                                {'$divide': ['$created_at', hour]},
                                {'$mod': [{'$divide': ['$created_at', hour]}, 1]}
                            ]
                        },
                        'state': '$state',
                    },
                    'count': {
                        '$sum': 1
                    }
                }
            },
        ])

        task_histogram = {}
        for item in histogram:
            print(item)
            primary = item['_id']
            state = primary.get('state')
            timestamp = hour * primary.get('interval')
            date = datetime.datetime.fromtimestamp(timestamp)
            date = str(date)
            if not task_histogram.get(timestamp):
                task_histogram[date] = {
                    'date': timestamp,
                    'error': 0,
                    'finish': 0,
                    'queued': 0,
                }

            task_histogram[date].update({
                state: item.get('count')
            })

        return task_histogram.values()

    def state_pies(self):
        task_state_pies = self.collection.aggregate([
            {
                '$group': {
                    '_id': {
                        'state': '$state',
                    },
                    'count': {
                        '$sum': 1
                    }
                }
            }
        ])

        task_state_pies = list(task_state_pies)
        for item in task_state_pies:
            item['state'] = item['_id']['state']

        return task_state_pies

    def duration(self, days=15):
        day_time = 86400
        duration = self.collection.aggregate([
            {
                '$match': {
                    'created_at': {
                        '$lt': time.time(),
                        '$gte': time.time() - days * day_time
                    },
                }
            },
            {
                '$group': {
                    '_id': None,
                    'avg': {
                        '$avg': '$duration'
                    },
                    'max': {
                        '$max': '$duration'
                    },
                    'min': {
                        '$min': '$duration'
                    },
                    'sum': {
                        '$sum': 1
                    }
                }
            }
        ])

        duration = list(duration)
        print(duration)
        if not duration:
            return {
                'avg': 0,
                'max': 0,
                'min': 0,
                'sum': 0,
            }


        return duration[0]


task_model = Task()
