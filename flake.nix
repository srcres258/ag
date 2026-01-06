{
  description = "Nix flake configurations for this project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    pyproject-nix
  }: flake-utils.lib.eachDefaultSystem (system: let
    pkgs = import nixpkgs {
      inherit system;
    };

    python = pkgs.python313;
    pythonPkgs = pkgs.python313Packages;

    project = pyproject-nix.lib.project.loadPyproject {
      projectRoot = ./.;
    };
    ag = pythonPkgs.buildPythonPackage (
      project.renderers.buildPythonPackage { inherit python; }
        // { src = ./.; }
    );
  in {
    packages.default = ag;

    apps.default = {
      type = "app";
      program = "${ag}/bin/ag";
    };

    devShells.default = pkgs.mkShell {
      buildInputs = [ python ] ++ ag.propagatedBuildInputs;
    };
  });
}
