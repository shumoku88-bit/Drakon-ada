#!/usr/bin/env tclsh
# New contributions: MIT (see LICENSE). Bootstrap adapted from the pinned
# Public Domain drakon_gen.tcl and scripts/generators.tcl; see NOTICE.
# Do not call upstream's
# generate_no_gui: it can swallow generator exceptions and return success.
set root [file normalize [file join [file dirname [info script]] ../..]]
set script_path [file join $root .upstream drakon_editor]
proc read_file {path} {
    set f [open $path r]
    try {read $f} finally {close $f}
}
set lock [read_file [file join $root upstream.lock]]
if {[string trim [exec git -C $script_path rev-parse HEAD]] ne [dict get $lock commit]} {
    error "Upstream commit mismatch"
}
if {[string trim [exec git -C $script_path status --porcelain --untracked-files=no]] ne ""} {
    error "Upstream tracked files are modified"
}
if {[read_file [file join $root generator ada.tcl]] ne
    [read_file [file join $script_path generators ada.tcl]]} {
    error "Plugin changed: rerun tools/setup.py"
}
package require msgcat
package require json::write
namespace import ::msgcat::mc
set use_log 0
foreach module {
    scripts/art scripts/utils scripts/generators scripts/graph scripts/auto
    scripts/model scripts/dedit scripts/back scripts/version scripts/search
    scripts/colors scripts/graph2 scripts/icon.links scripts/newfor scripts/highlight
    generators/c generators/cpp generators/cycle_body generators/node_sorter
    generators/python generators/tcl structure/struct structure/tables
    structure/tables_tcl structure/tables_cs structure/tables_c
} {
    source [file join $script_path $module.tcl]
}
load_sqlite
load_generators
namespace eval mw {proc set_status {ignored} {}}

if {[llength $argv] != 2} {
    puts stderr "Usage: tclsh generate.tcl SOURCE.drn OUTPUT_DIRECTORY"
    exit 1
}
lassign $argv src out
if {[catch {
    lassign [mod::open db [file normalize $src] drakon] ignored message
    if {$message ne ""} {error $message}
    mwc::init db
    array set properties [mwc::get_file_properties]
    if {![info exists properties(language)] || $properties(language) ni {Ada SPARK}} {
        error "Expected Ada or SPARK file language"
    }
    namespace eval ::current_file_generation_info {}
    set ::current_file_generation_info::language $properties(language)
    set ::current_file_generation_info::generator gen_ada::generate
    newfor::clear
    graph::verify_all db
    if {[graph::errors_occured]} {error [graph::get_error_list]}
    file mkdir $out
    gen_ada::generate db gdb [file join [file normalize $out] [file tail $src]]
    if {[graph::errors_occured]} {error [graph::get_error_list]}
} message options]} {
    puts stderr [dict get $options -errorinfo]
    exit 1
}
