{
  description = "Python library to read GnuCash SQL files";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = inputs @ { self, ... }:
    inputs.flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import (inputs.nixpkgs) { inherit system; };

      inherit (pkgs) stdenv;

      buildInputs = with pkgs; [
        poetry
        ruff
        python3
      ];
    in {
        devShell = pkgs.mkShell {
            name = "pygnucash-shell";
            buildInputs = buildInputs ++ (with pkgs; [
                ruff
                mypy
                sqlite
            ]);
        };
    });
}
