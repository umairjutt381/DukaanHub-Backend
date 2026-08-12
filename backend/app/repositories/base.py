from sqlalchemy.orm import Session


class RepositoryBase:
    def __init__(self, db: Session):
        self.db = db

