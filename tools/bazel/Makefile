# Bazel uses the maintained upstream Makefiles and Debian's selected config.
# No Debian packaging command or host installation is part of this frontend.
# Debian enables -Wall; its selected CONFIG_EAPOL_TEST makes warnings fatal.
# Do not add the shared toolchain's extra warning class to that legacy contract.
WPA_NATIVE_FLAGS := -O2 -g -MMD -Wall -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=3 -fstack-protector-strong -Wformat -Werror=format-security -Wno-error=array-bounds -Wno-deprecated-declarations -Wno-use-after-free
export CFLAGS := $(filter-out -Wextra -D_FORTIFY_SOURCE=%,$(CFLAGS)) $(CPPFLAGS) $(WPA_NATIVE_FLAGS) -Wno-discarded-qualifiers
export CXXFLAGS := $(filter-out -Wextra -D_FORTIFY_SOURCE=%,$(CXXFLAGS)) $(CPPFLAGS) $(WPA_NATIVE_FLAGS)
# Both foreign_cc flag sets contain the same target includes and C flags;
# CXXFLAGS additionally owns C++ standard-library headers. Keep that baseline
# once in C++ commands, then retain the upstream Makefile's later flags in order.
export WPA_CXX_BASE_CFLAGS := $(CFLAGS)
# Resolve DT_NEEDED entries through the same declared owner/runtime library
# directories; native ld does not use -L for shared libraries' dependencies.
# Keep the transitive search list in a response file instead of doubling the
# exported LDFLAGS environment entry past Linux's per-string size limit.
WPA_LINK_RESPONSE := $(CURDIR)/.bazel-wpa-rpath-link.rsp
$(file >$(WPA_LINK_RESPONSE),$(foreach directory,$(sort $(patsubst -L%,%,$(filter -L%,$(LDFLAGS)))),-Xlinker -rpath-link -Xlinker $(directory)))
export LDFLAGS := $(LDFLAGS) @$(WPA_LINK_RESPONSE) -Wl,--as-needed -Wl,-z,relro -Wl,-z,now -L$(CURDIR)/bazel-libs
export EXTRA_CFLAGS :=
# CcInfo supplies the selected include directories, including PCSC and D-Bus.
export PCSC_CFLAGS :=
export DBUS_INCLUDE := -DCONFIG_BAZEL_DECLARED_DBUS
export DBUS_LIBS := -ldbus-1
export LIBNL_INC := $(CURDIR)/bazel-libs
export CONFIG_NO_GITVER := y
export BINDIR := /sbin
export V := 1

.PHONY: all install
all: wpa_supplicant/.config
	mkdir -p bazel-libs
	ln -sf "$(SONIC_COMMON_LIBRARY)" bazel-libs/libswsscommon.so
	ln -sf "$(SONIC_NL_LIBRARY)" bazel-libs/libnl-3.so
	ln -sf "$(SONIC_GENL_LIBRARY)" bazel-libs/libnl-genl-3.so
	ln -sf "$(SONIC_ROUTE_LIBRARY)" bazel-libs/libnl-route-3.so
	$(MAKE) -C wpa_supplicant all

wpa_supplicant/.config: debian/config/wpasupplicant/linux
	cp $< $@

install:
	install -d $(PREFIX)/bin $(PREFIX)/systemd $(PREFIX)/dbus
	install -m 0755 wpa_supplicant/wpa_supplicant wpa_supplicant/wpa_cli wpa_supplicant/wpa_passphrase $(PREFIX)/bin/
	install -m 0644 wpa_supplicant/systemd/*.service $(PREFIX)/systemd/
	install -m 0644 wpa_supplicant/dbus/fi.w1.wpa_supplicant1.service $(PREFIX)/dbus/


# Keep the upstream internal-crypto/container tests separate from production
# outputs. They deliberately exercise the upstream test implementations;
# production TLS continues to use the selected source-owned OpenSSL library.
.PHONY: upstream-tests install-upstream-tests
UPSTREAM_TESTS := test-aes test-base64 test-list test-md4 test-milenage test-rc4 test-rsa-sig-ver test-sha1 test-sha256 test-x509v3 test-https test-https_server
upstream-tests:
	$(MAKE) -C tests $(UPSTREAM_TESTS)

install-upstream-tests:
	install -d $(PREFIX)/bin
	$(foreach name,$(UPSTREAM_TESTS),install -m 0755 tests/$(name) $(PREFIX)/bin/;)
