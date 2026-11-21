#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VC の _joystick.py の機械チェック (PR の自動確認用)

使い方:
    python check_joystick.py <新しい _joystick.py> [<元の _joystick.py>]

見ること (02_作業ルール.md の 3 章・4 章の決まり):
  1. Python 3.5 で使えない文法がないか
       - f 文字列
       - 型注釈 (引数・戻り値・変数)
       - := (セイウチ演算子)
       - 数値の桁区切り 1_000
  2. ファイルが CRLF か (LF の行が混ざっていないか)
  3. APP_VERSION が上がっているか (元のファイルを渡したときだけ。
     _joystick.py 自体が変わっていないときは見ない)

終了コード: 問題なし 0 / 問題あり 1 / 読めない 2
本体の動きは見ない。実機の確かめは人が行う (02 の 5 章)。
"""
import ast
import io
import re
import sys
import tokenize

PROBLEMS = []


def problem(msg):
    PROBLEMS.append(msg)


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def check_py35_syntax(src_text, label):
    try:
        tree = ast.parse(src_text)
    except SyntaxError as e:
        problem('%s: 構文エラー (行 %s): %s' % (label, e.lineno, e.msg))
        return

    for node in ast.walk(tree):
        line = getattr(node, 'lineno', '?')
        if isinstance(node, ast.JoinedStr):
            problem('%s:%s: f 文字列 (Python 3.5 では使えない)' % (label, line))
        elif isinstance(node, ast.NamedExpr):
            problem('%s:%s: := は使えない (Python 3.5)' % (label, line))
        elif isinstance(node, ast.AnnAssign):
            problem('%s:%s: 変数の型注釈は使えない (Python 3.5)' % (label, line))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                problem('%s:%s: 戻り値の型注釈は使えない (Python 3.5)' % (label, line))
            args = node.args
            every = list(args.args) + list(args.kwonlyargs) + list(args.posonlyargs or [])
            if args.vararg is not None:
                every.append(args.vararg)
            if args.kwarg is not None:
                every.append(args.kwarg)
            for a in every:
                if a.annotation is not None:
                    problem('%s:%s: 引数の型注釈は使えない (Python 3.5)' % (label, line))
                    break

    # 桁区切りの 1_000 は tokenize で見る
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src_text).readline):
            if tok.type == tokenize.NUMBER and '_' in tok.string:
                problem('%s:%s: 数値の桁区切り %s は使えない (Python 3.5)' % (label, tok.start[0], tok.string))
    except tokenize.TokenError:
        pass


def check_crlf(raw, label):
    # 改行は CRLF だけであるべき (LF だけの行があれば指摘)
    lf_only = len(re.findall(rb'(?<!\r)\n', raw))
    if lf_only:
        problem('%s: LF だけの行が %d 行ある (ファイルは CRLF)' % (label, lf_only))


APP_VERSION_RE = re.compile(rb"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", re.M)


def app_version(raw):
    m = APP_VERSION_RE.search(raw)
    return m.group(1).decode('ascii', 'replace') if m else None


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    new_path = argv[1]
    base_path = argv[2] if len(argv) >= 3 else None
    try:
        new_raw = read_bytes(new_path)
    except OSError as e:
        print('読めない: %s (%s)' % (new_path, e))
        return 2

    new_text = new_raw.decode('utf-8', 'replace')
    check_py35_syntax(new_text, new_path)
    check_crlf(new_raw, new_path)

    new_ver = app_version(new_raw)
    if new_ver is None:
        problem('%s: APP_VERSION が見つからない' % new_path)

    if base_path:
        try:
            base_raw = read_bytes(base_path)
        except OSError as e:
            print('読めない: %s (%s)' % (base_path, e))
            return 2
        base_ver = app_version(base_raw)
        if new_raw == base_raw:
            # コードを変えない PR (CI や文書だけの変更) では上げ忘れを見ない
            print('_joystick.py は変更なし (APP_VERSION は見ない): %s' % new_ver)
        elif new_ver is not None and new_ver == base_ver:
            problem('APP_VERSION が上がっていない (%s のまま)' % new_ver)
        if new_raw != base_raw:
            print('APP_VERSION: %s -> %s' % (base_ver, new_ver))
    else:
        print('APP_VERSION: %s (元のファイルがないので上がったかは見ない)' % new_ver)

    if PROBLEMS:
        for p in PROBLEMS:
            print('NG  ' + p)
        return 1
    print('OK  文法 (3.5)・改行 (CRLF)・APP_VERSION を確認')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
