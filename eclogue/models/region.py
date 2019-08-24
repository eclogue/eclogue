from eclogue.model import Model, db


class Region(Model):

    name = 'regions'

    def __init__(self, name='regions'):
        super(Region, self).__init__(name)


region_model = Region()
