from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, write_to_textfile, REGISTRY, generate_latest


class Client(object):

    """
    TODO(@shisang)
    """
    def counter(self, metric_name, document, lable_names, lable_values, increment):
        counter = Counter(metric_name, document, lable_names)
        counter.labels(lable_values).inc(increment)

    def histogram(self, metric_name, document, lable_names, lable_values, observe):
        histgram = Histogram(metric_name, document, lable_names)
        histgram.labels(lable_values).observe(observe)

