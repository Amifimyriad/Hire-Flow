from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


def configure_table(
    table: QTableWidget,
    headers: list[str],
    *,
    column_widths: list[int] | None = None,
    stretch_last: bool = True,
) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setSectionsMovable(True)
    table.horizontalHeader().setSectionsClickable(True)
    table.horizontalHeader().setFixedHeight(44)
    table.horizontalHeader().setMinimumSectionSize(88)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSortingEnabled(False)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setCornerButtonEnabled(False)
    table.setMouseTracking(True)
    table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setStretchLastSection(stretch_last)
    table.verticalHeader().setDefaultSectionSize(48)
    table.verticalHeader().setMinimumSectionSize(44)
    table.setMinimumHeight(220)
    if column_widths:
        apply_column_widths(table, column_widths)
        table.setMinimumWidth(sum(column_widths) + 48)


def apply_column_widths(table: QTableWidget, column_widths: list[int]) -> None:
    for index, width in enumerate(column_widths[: table.columnCount()]):
        table.setColumnWidth(index, width)


def set_table_rows(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            item = QTableWidgetItem(value)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemNeverHasChildren
            )
            table.setItem(row_index, column_index, item)


def format_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone().strftime("%b %d, %H:%M")
    except ValueError:
        return value
