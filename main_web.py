if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the local OK-WW web interface")
    parser.add_argument("--browser", action="store_true",
                        help="Open the interface in the default browser instead of an embedded window")
    args, _ = parser.parse_known_args()
    from config import config
    from ok import OK

    config = config
    config["gui"] = {
        "type": "web",
        "launch_mode": "browser" if args.browser else "pywebview",
    }
    ok = OK(config)
    ok.start()
