"""Unit tests of the Structured Text VM itself (language semantics)."""
import pytest

from farmsim.stvm import STError, STMachine, parse_time


def prog(body, decls="", fbs=""):
    return STMachine(f"""{fbs}
PROGRAM P
VAR
{decls}
END_VAR
{body}
END_PROGRAM""", cycle_ms=10)


def test_time_literals():
    assert parse_time("T#1m30s") == 90_000
    assert parse_time("t#500ms") == 500
    assert parse_time("TIME#1d2h") == 93_600_000
    assert parse_time("T#1.5s") == 1500


def test_ton_timing():
    vm = prog("t(IN := go, PT := T#100ms); q := t.Q;", "go : BOOL; q : BOOL; t : TON;")
    vm["go"] = True
    vm.scan(10)                 # first scan starts timing, 9 more = 90 ms
    assert not vm["q"]
    vm.scan(1)
    assert vm["q"] and vm.fb("t")["ET"] == 100
    vm["go"] = False
    vm.scan()
    assert not vm["q"] and vm.fb("t")["ET"] == 0


def test_tof_and_r_trig():
    vm = prog("t(IN := x, PT := T#50ms); r(CLK := x); q := t.Q; e := r.Q;",
              "x, q, e : BOOL; t : TOF; r : R_TRIG;")
    vm["x"] = True
    vm.scan()
    assert vm["q"] and vm["e"]
    vm.scan()
    assert not vm["e"]
    vm["x"] = False
    vm.scan(5)
    assert vm["q"]
    vm.scan(1)
    assert not vm["q"]


def test_integer_semantics():
    vm = prog("a := -7 / 2; b := -7 MOD 2; c := 32767 + 1; w := 16#FFFF + 1;",
              "a, b, c : INT; w : WORD;")
    vm.scan()
    assert (vm["a"], vm["b"], vm["c"], vm["w"]) == (-3, -1, -32768, 0)


def test_real_to_int_rounds_half_away_from_zero():
    vm = prog("a := REAL_TO_INT(2.5); b := REAL_TO_INT(-2.5); c := REAL_TO_INT(2.4);", "a, b, c : INT;")
    vm.scan()
    assert (vm["a"], vm["b"], vm["c"]) == (3, -3, 2)


def test_case_lists_ranges_and_else():
    vm = prog("""
CASE s OF
  1, 2: r := 10;
  3..5: r := 20;
ELSE r := 99;
END_CASE;""", "s, r : INT;")
    for s, r in ((1, 10), (2, 10), (4, 20), (7, 99)):
        vm["s"] = s
        vm.scan()
        assert vm["r"] == r


def test_user_function_block_and_loops():
    vm = prog("acc(N := 5); out := acc.SUM;", "acc : FB_Sum; out : INT;", fbs="""
FUNCTION_BLOCK FB_Sum
VAR_INPUT N : INT; END_VAR
VAR_OUTPUT SUM : INT; END_VAR
VAR i : INT; END_VAR
SUM := 0;
FOR i := 1 TO N DO
  SUM := SUM + i;
END_FOR;
WHILE SUM > 100 DO EXIT; END_WHILE;
END_FUNCTION_BLOCK""")
    vm.scan()
    assert vm["out"] == 15


@pytest.mark.parametrize("body, decls, msg", [
    ("r := 1;", "r : REAL;", "cannot assign INT"),
    ("i := r;", "i : INT; r : REAL;", "cannot assign REAL"),
    ("r := r + 1;", "r : REAL;", "mixing REAL and integer"),
    ("b := 1;", "b : BOOL;", "cannot assign INT"),
    ("IF i THEN i := 0; END_IF;", "i : INT;", "not BOOL"),
    ("x := 1;", "", "undeclared variable X"),
    ("C := 2;", "", "constant"),
])
def test_strict_typing_errors(body, decls, msg):
    with pytest.raises(STError, match=msg):
        src_decls = decls + ("\nEND_VAR\nVAR CONSTANT C : INT := 1;" if "C :=" in body else "")
        prog(body, src_decls).scan()


def test_errors_report_line_numbers():
    with pytest.raises(STError, match=r"line 7"):
        prog("i := 1;\nr := r / 0.0;", "i : INT; r : REAL;").scan()


def test_exp_and_ln():
    vm = prog("r := EXP(1.0); q := LN(r);", "r : REAL; q : REAL;")
    vm.scan()
    assert vm["r"] == pytest.approx(2.718281828) and vm["q"] == pytest.approx(1.0)


def test_lean_mode_matches_strict():
    """Lean mode drops run-time type checks only: same program, same results."""
    from farmsim.bench import Bench
    runs = []
    for strict in (True, False):
        b = Bench(clock="06:29", strict=strict)
        b.run(150)
        runs.append({k: v for k, v in b.vm.program.vars.items() if not hasattr(v, "vars")})
    assert runs[0] == runs[1]


def test_lean_mode_keeps_integer_wraparound():
    vm = STMachine(SRC_WRAP, strict=False)
    vm.scan()
    assert vm["u"] == 0 and vm["i"] == -32768 and vm["w"] == 0x0000


SRC_WRAP = """
PROGRAM P
VAR u : UINT := 65535; i : INT := 32767; w : WORD := 16#8000; END_VAR
    u := u + 1;
    i := i + 1;
    w := SHL(w, 1);
END_PROGRAM
"""


def test_greenhouse_program_loads():
    from farmsim.bench import ST_FILE
    vm = STMachine(ST_FILE.read_text(encoding="utf-8"))
    assert vm.cycle_ms == 50
    assert vm.program_type.name == "GREENHOUSE"
    assert vm.located["%QW102"] == "P313_REF"
    assert vm.located["%IW115"] == "CLOCK_MIN"
    mw = sorted(int(a[3:]) for a in vm.located if a.startswith("%MW"))
    assert mw[0] == 0 and mw[-1] == 139
