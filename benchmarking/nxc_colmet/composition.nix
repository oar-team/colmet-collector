{ pkgs, nur, ... }: {
  nodes = {
    collector = { pkgs, nur, ... }:
      {
        environment.systemPackages = [ pkgs.nur.repos.kapack.colmet-collector ];
      };
    compute = { pkgs, ... }:
      {
        environment.systemPackages = with pkgs; [ openmpi nur.repos.kapack.npb nur.repos.kapack.colmet-rs ];
      };
  };
  testScript = ''
    foo.succeed("true")
    '';
}
