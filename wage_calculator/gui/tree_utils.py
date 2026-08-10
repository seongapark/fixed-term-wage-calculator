"""Treeview 컬럼 너비를 헤더/셀 내용 길이에 맞춰 컬럼별로 자동 조정하는 유틸.

모든 컬럼을 같은 width로 고정하면 조사명·계약기간처럼 값이 긴 컬럼이
화면에서 잘려 보인다. 데이터가 채워진 뒤 이 함수를 호출하면 컬럼마다
실제 폰트 렌더 폭(한글 폭 포함)을 측정해 그 컬럼만 필요한 만큼 넓힌다.
"""
import tkinter.font as tkfont


def autosize_columns(tree, columns, headers=None, min_width=60, max_width=420, padding=24):
    font = tkfont.nametofont("TkDefaultFont")
    heading_font = tkfont.nametofont("TkHeadingFont") if "TkHeadingFont" in tkfont.names() else font

    for col in columns:
        header_text = headers[col] if headers else tree.heading(col, "text")
        widest = heading_font.measure(str(header_text))
        for iid in tree.get_children():
            value = tree.set(iid, col)
            widest = max(widest, font.measure(str(value)))
        tree.column(col, width=max(min_width, min(max_width, widest + padding)))
