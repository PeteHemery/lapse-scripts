#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
"""
Prelapse front end.
Choose from sub commands available to create and modify files
 required to play and create music video files from image sequences.

"""
import sys
sys.dont_write_bytecode = True

import prelapse


def main():
  parser = prelapse.setupArgParsing()
  args = parser.parse_args()
  prelapse.handleParsedArgs(parser, args)


if __name__ == "__main__":
  main()

