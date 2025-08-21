#!/bin/bash
$(sed -i 's/\r$//' ./*.sh && chmod +x ./*.sh)
