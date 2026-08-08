from .models import ThsBoard, ThsBoardConstituent, ThsStockRelation


BOARD_COLUMNS = tuple(ThsBoard.__dataclass_fields__)
CONSTITUENT_COLUMNS = tuple(ThsBoardConstituent.__dataclass_fields__)
RELATION_COLUMNS = tuple(ThsStockRelation.__dataclass_fields__)


class ThsRepository:
    def __init__(self, query):
        self._query = query

    def boards(self, board_type=None):
        conditions = []
        params = []
        if board_type is not None:
            conditions.append("`board_type` = %s")
            params.append(str(board_type))
        rows = self._select(
            "ths_boards",
            BOARD_COLUMNS,
            conditions,
            params,
            "`board_type`, `board_name`, `board_code`",
        )
        return [ThsBoard(**dict(row)) for row in rows]

    def board_constituents(self, board_code=None, board_type=None, stock_code=None):
        conditions = []
        params = []
        for column, value in (
            ("board_code", board_code),
            ("board_type", board_type),
            ("stock_code", stock_code),
        ):
            if value is not None:
                conditions.append(f"`{column}` = %s")
                params.append(str(value))
        rows = self._select(
            "ths_board_constituents",
            CONSTITUENT_COLUMNS,
            conditions,
            params,
            "`board_code`, `stock_code`",
        )
        return [ThsBoardConstituent(**dict(row)) for row in rows]

    def stock_relations(self, stock_code=None):
        conditions = []
        params = []
        if stock_code is not None:
            conditions.append("`stock_code` = %s")
            params.append(str(stock_code))
        rows = self._select(
            "ths_stock_relations",
            RELATION_COLUMNS,
            conditions,
            params,
            "`stock_code`",
        )
        return [ThsStockRelation(**dict(row)) for row in rows]

    def _select(self, table, columns, conditions, params, order_by):
        column_sql = ", ".join(f"`{column}`" for column in columns)
        sql = f"SELECT {column_sql} FROM `{table}`"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += f" ORDER BY {order_by}"
        return self._query(
            sql,
            params=tuple(params) if params else None,
            fetch=True,
        ) or []
