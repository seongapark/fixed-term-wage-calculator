"""6장-1: 파일 업로드 화면."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class UploadScreen(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.a_path = tk.StringVar()
        self.b_path = tk.StringVar()
        self.prev_path = tk.StringVar()

        ttk.Label(self, text="통계조사관 임금계산", font=("", 16, "bold")).pack(pady=(30, 20))

        row1 = ttk.Frame(self)
        row1.pack(fill="x", padx=40, pady=8)
        ttk.Label(row1, text="개인정보 파일 (A)", width=18).pack(side="left")
        ttk.Entry(row1, textvariable=self.a_path, width=50).pack(side="left", padx=6)
        ttk.Button(row1, text="찾아보기", command=self._pick_a).pack(side="left")

        row2 = ttk.Frame(self)
        row2.pack(fill="x", padx=40, pady=8)
        ttk.Label(row2, text="근무상황 파일 (B)", width=18).pack(side="left")
        ttk.Entry(row2, textvariable=self.b_path, width=50).pack(side="left", padx=6)
        ttk.Button(row2, text="찾아보기", command=self._pick_b).pack(side="left")

        row3 = ttk.Frame(self)
        row3.pack(fill="x", padx=40, pady=8)
        ttk.Label(row3, text="전월 임금내역 (선택)", width=18).pack(side="left")
        ttk.Entry(row3, textvariable=self.prev_path, width=50).pack(side="left", padx=6)
        ttk.Button(row3, text="찾아보기", command=self._pick_prev).pack(side="left")
        ttk.Label(self, text="※ 비워두면 소급계산을 하지 않습니다.", foreground="gray").pack()

        ttk.Button(self, text="다음", command=self._next).pack(pady=30)

    def _pick_a(self):
        path = filedialog.askopenfilename(title="개인정보 파일 선택", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.a_path.set(path)

    def _pick_b(self):
        path = filedialog.askopenfilename(title="근무상황 파일 선택", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.b_path.set(path)

    def _pick_prev(self):
        path = filedialog.askopenfilename(title="전월 임금내역 파일 선택", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.prev_path.set(path)

    def _next(self):
        if not self.a_path.get() or not self.b_path.get():
            messagebox.showwarning("파일 필요", "개인정보(A), 근무상황(B) 파일을 모두 선택하세요.")
            return
        try:
            self.app.load_files(self.a_path.get(), self.b_path.get(), self.prev_path.get() or None)
        except Exception as e:
            messagebox.showerror("파일 로드 오류", str(e))
            return
        self.app.after_upload()
