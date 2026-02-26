import main


def test_extract_params_detects_billions():
    assert main.extract_params("llama-3.1-8b-instruct") == "8B"


def test_extract_params_returns_dash_when_missing():
    assert main.extract_params("my-model") == "-"


def test_format_likes_compacts_thousands_and_millions():
    assert main.format_likes(1500) == "1.5K"
    assert main.format_likes(2_500_000) == "2.5M"


def test_determine_use_case_coding_priority():
    assert "Coding" in main.determine_use_case("deepseek-coder-7b")


def test_calculate_fit_perfect_gpu():
    specs = {
        "has_gpu": True,
        "vram_free": 12.0,
        "ram_free": 16.0,
    }
    fit, mode, resource = main.calculate_fit(7.0, specs)
    assert "Perfect" in fit
    assert "GPU" in mode
    assert resource == "VRAM"


def test_calculate_fit_no_fit_when_memory_low():
    specs = {
        "has_gpu": False,
        "vram_free": 0.0,
        "ram_free": 2.0,
    }
    fit, mode, resource = main.calculate_fit(8.0, specs)
    assert "No Fit" in fit
    assert resource == "Yetersiz"
