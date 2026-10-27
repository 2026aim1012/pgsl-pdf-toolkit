from pdf_toolkit.gui.explorer import move_item

def test_move_down():
    assert move_item(["a", "b", "c"], 0, 1) == (["b", "a", "c"], 1)

def test_move_up_at_top_is_noop():
    assert move_item(["a", "b"], 0, -1) == (["a", "b"], 0)

def test_move_down_at_bottom_is_noop():
    assert move_item(["a", "b"], 1, 1) == (["a", "b"], 1)