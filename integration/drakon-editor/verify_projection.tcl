#!/usr/bin/env tclsh
# Verify an O3b-generated DRAKON document with the exact pinned upstream graph
# extractor. This does not invoke any code generator.
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

package require msgcat
namespace import ::msgcat::mc
set use_log 0

# Keep the verifier bootstrap aligned with the already-qualified headless
# generator bootstrap, but do not load or invoke Drakon-ada's Ada generator.
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
namespace eval mw {proc set_status {ignored} {}}

if {[llength $argv] != 1} {
    puts stderr "Usage: tclsh verify_projection.tcl FILE.drn"
    exit 1
}
set src [file normalize [lindex $argv 0]]

if {[catch {
    lassign [mod::open db $src drakon] ignored message
    if {$message ne ""} {error $message}
    mwc::init db

    array set properties [mwc::get_file_properties]
    if {![info exists properties(language)] || $properties(language) ne "SPARK"} {
        error "Expected generated observation file language SPARK"
    }

    newfor::clear
    graph::verify_all db
    if {[graph::errors_occured]} {
        error [join [graph::get_error_list] "\n"]
    }

    set diagram_count [db onecolumn {select count(*) from diagrams}]
    if {$diagram_count != 1} {
        error "Expected exactly one projected diagram, got $diagram_count"
    }

    set map_count [db onecolumn {
        select count(*) from diagram_info
        where name = 'drakon-ada/drn-projection-map/v1'
    }]
    if {$map_count != 1} {
        error "Missing Drakon-ada projection map metadata"
    }

    db close
} message options]} {
    puts stderr [dict get $options -errorinfo]
    exit 1
}

puts "PASS: pinned DRAKON Editor accepted projected SQLite graph"
