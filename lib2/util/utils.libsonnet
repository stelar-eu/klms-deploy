// Miscellaneous helper functions shared across lib2 Jsonnet code.
{
  // Shared logic for generating TLS secret names based on subdomain and root
  get_secret_name(subdomain, root):: (
    local full_domain = subdomain + "." + root;
    // Changed std.substring to std.substr
    local hash = std.substr(std.md5(full_domain), 0, 5);
    subdomain + "-tls-" + hash
  ),
}