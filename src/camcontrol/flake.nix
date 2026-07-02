{
  description = "camcontrol — stream head-tracking events over a TCP port";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      # Native libraries the opencv-python / mediapipe wheels dlopen at
      # runtime. Nix's Python can't find these via the system loader, so we
      # expose them through LD_LIBRARY_PATH. If a `nix develop` run reports a
      # missing `.so`, add the providing package here.
      runtimeLibs = with pkgs; [
        stdenv.cc.cc.lib # libstdc++, libgcc_s
        zlib
        libGL # libGL.so.1 (opencv, mediapipe)
        glib # libgthread / libglib (opencv)
      ];
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          python311
          uv
        ];

        # Use the Nix-provided interpreter instead of uv's standalone CPython
        # download, which is a manylinux build that won't run on NixOS.
        UV_PYTHON = "${pkgs.python311}/bin/python3.11";
        UV_PYTHON_DOWNLOADS = "never";

        LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath runtimeLibs;

        shellHook = ''
          echo "camcontrol dev shell — Python $(python3 --version 2>&1 | cut -d' ' -f2), uv $(uv --version | cut -d' ' -f2)"
          echo "  uv run camcontrol calibrate   # 4-corner calibration"
          echo "  uv run camcontrol serve        # stream events on 127.0.0.1:8765"
          echo "  uv run pytest                  # tests"
        '';
      };
    };
}
