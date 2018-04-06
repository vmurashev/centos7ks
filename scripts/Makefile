DIR_HERE := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
OUTPUT_DIR := $(abspath $(DIR_HERE)../output)

OUTPUT_ISO_NAME := centos7
OUTPUT_ISO_FILE_PATH := $(OUTPUT_DIR)/$(OUTPUT_ISO_NAME).iso
YUMDATA_STAMP := $(OUTPUT_DIR)/yumdata.stamp

SCRIPT_GEN_ISO := $(DIR_HERE)/create-iso.sh
GEN_ISO_EXTRA_DEPENDS := $(DIR_HERE)/create-iso.sh $(DIR_HERE)/iso-ks.cfg $(DIR_HERE)/autostart.sh $(DIR_HERE)/isolinux.cfg $(DIR_HERE)/grub_efi.cfg

SCRIPT_GEN_YUMDATA := $(DIR_HERE)/create-yumdata.sh
GEN_YUMDATA_EXTRA_DEPENDS := $(DIR_HERE)/packages-live.lst $(DIR_HERE)/create-yumdata.sh $(DIR_HERE)/strip-groups-info.py

all: $(OUTPUT_ISO_FILE_PATH)

$(YUMDATA_STAMP): $(GEN_YUMDATA_EXTRA_DEPENDS)
	mkdir -p $(OUTPUT_DIR)
	$(SCRIPT_GEN_YUMDATA) $(OUTPUT_DIR)
	touch $(YUMDATA_STAMP)

$(OUTPUT_ISO_FILE_PATH): $(YUMDATA_STAMP) $(GEN_ISO_EXTRA_DEPENDS)
	mkdir -p $(OUTPUT_DIR)
	rm -f $(OUTPUT_DIR)/iso-ks.cfg
	rm -f $(OUTPUT_DIR)/autostart.sh
	rm -f $(OUTPUT_DIR)/isolinux.cfg
	cp $(DIR_HERE)/iso-ks.cfg $(OUTPUT_DIR)
	cp $(DIR_HERE)/autostart.sh $(OUTPUT_DIR)
	cp $(DIR_HERE)/isolinux.cfg $(OUTPUT_DIR)
	cp $(DIR_HERE)/grub_efi.cfg $(OUTPUT_DIR)
	$(SCRIPT_GEN_ISO) $(OUTPUT_ISO_FILE_PATH)
