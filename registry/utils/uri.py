"""
Regex for URIs

These regex are directly derived from the collected ABNF in RFC3986
(except for DIGIT, ALPHA and HEXDIG, defined by RFC2234).

They should be processed with re.VERBOSE.

Thanks Mark Nottingham for this code - https://gist.github.com/138549
"""
import re

# basics
DIGIT = r"[\x30-\x39]"
ALPHA = r"[\x41-\x5A\x61-\x7A]"
HEXDIG = r"[\x30-\x39A-Fa-f]"

# pct-encoded = "%" HEXDIG HEXDIG
pct_encoded = r" %% %(HEXDIG)s %(HEXDIG)s" % locals()

# unreserved = ALPHA / DIGIT / "-" / "." / "_" / "~"
unreserved = r"(?: %(ALPHA)s | %(DIGIT)s | \- | \. | _ | ~ )" % locals()

# gen-delims = ":" / "/" / "?" / "#" / "[" / "]" / "@"
gen_delims = r"(?: : | / | \? | \# | \[ | \] | @ )"

# sub-delims = "!" / "$" / "&" / "'" / "(" / ")" / "*" / "+" / "," / ";" / "="
sub_delims = r"""(?: ! | \$ | & | ' | \( | \) | \* | \+ | , | ; | = )"""

# pchar = unreserved / pct-encoded / sub-delims / ":" / "@"
pchar = r"(?: %(unreserved)s | %(pct_encoded)s | %(sub_delims)s | : | @ )" % locals()

# reserved = gen-delims / sub-delims
reserved = r"(?: %(gen_delims)s | %(sub_delims)s )" % locals()

# scheme
scheme = r"%(ALPHA)s (?: %(ALPHA)s | %(DIGIT)s | \+ | \- | \. )*" % locals()

# authority
dec_octet = r"""(?: %(DIGIT)s |
                    [\x31-\x39] %(DIGIT)s |
                    1 %(DIGIT)s{2} |
                    2 [\x30-\x34] %(DIGIT)s |
                    25 [\x30-\x35]
                )
""" % locals()

IPv4address = r"%(dec_octet)s \. %(dec_octet)s \. %(dec_octet)s \. %(dec_octet)s" % locals()

IPv6address = r"([A-Fa-f0-9:]+[:$])[A-Fa-f0-9]{1,4}"

IPvFuture = r"v %(HEXDIG)s+ \. (?: %(unreserved)s | %(sub_delims)s | : )+" % locals()

IP_literal = r"\[ (?: %(IPv6address)s | %(IPvFuture)s ) \]" % locals()

reg_name = r"(?: %(unreserved)s | %(pct_encoded)s | %(sub_delims)s )*" % locals()

userinfo = r"(?: %(unreserved)s | %(pct_encoded)s | %(sub_delims)s | : )" % locals()

host = r"(?: %(IP_literal)s | %(IPv4address)s | %(reg_name)s )" % locals()

port = r"(?: %(DIGIT)s )*" % locals()

authority = r"(?: %(userinfo)s @)? %(host)s (?: : %(port)s)?" % locals()

# Path
segment = r"%(pchar)s*" % locals()
segment_nz = r"%(pchar)s+" % locals()
segment_nz_nc = r"(?: %(unreserved)s | %(pct_encoded)s | %(sub_delims)s | @ )+" % locals()

path_abempty = r"(?: / %(segment)s )*" % locals()
path_absolute = r"/ (?: %(segment_nz)s (?: / %(segment)s )* )?" % locals()
path_noscheme = r"%(segment_nz_nc)s (?: / %(segment)s )*" % locals()
path_rootless = r"%(segment_nz)s (?: / %(segment)s )*" % locals()
path_empty = r""

path = r"""(?: %(path_abempty)s |
               %(path_absolute)s |
               %(path_noscheme)s |
               %(path_rootless)s |
               %(path_empty)s
            )
""" % locals()

# Query and Fragment
query = r"(?: %(pchar)s | / | \? )*" % locals()
fragment = r"(?: %(pchar)s | / | \? )*" % locals()

# URIs
hier_part = r"""(?: (?: // %(authority)s %(path_abempty)s ) |
                    %(path_absolute)s |
                    %(path_rootless)s |
                    %(path_empty)s
                )
""" % locals()

relative_part = r"""(?: (?: // %(authority)s %(path_abempty)s ) |
                        %(path_absolute)s |
                        %(path_noscheme)s |
                        %(path_empty)s
                    )
""" % locals()

relative_ref = r"%(relative_part)s (?: \? %(query)s)? (?: \# %(fragment)s)?" % locals()

URI = r"^(?: %(scheme)s : %(hier_part)s (?: \? %(query)s )? (?: \# %(fragment)s )? )$" % locals()

URI_reference = r"^(?: %(URI)s | %(relative_ref)s )$" % locals()

absolute_URI = r"^(?: %(scheme)s : %(hier_part)s (?: \? %(query)s )? )$" % locals()

def is_uri(uri):
    return re.match(URI, uri, re.VERBOSE)

def is_uri_reference(uri):
    return re.match(URI_reference, uri, re.VERBOSE)

def is_absolute_uri(uri):
    return re.match(absolute_URI, uri, re.VERBOSE) 