from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from eclogue.config import Config


engine = create_engine(Config.DB_URI, convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
def to_dict(self):
  return {c.name: getattr(self, c.name, None) for c in self.__table__.columns}
Base = declarative_base()
Base.query = db_session.query_property()
Base.to_dict = to_dict


def init_db():
    # 在这里导入所有的可能与定义模型有关的模块，这样他们才会合适地
    # 在 metadata 中注册。否则，您将不得不在第一次执行 init_db() 时
    # 先导入他们。
    import eclogue.model
    Base.metadata.create_all(bind=engine)
