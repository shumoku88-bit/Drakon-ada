#!/usr/bin/env tclsh
# Verify an O3b/O3c-generated DRAKON document with the exact pinned upstream
# graph extractor, then compare its interpreted control flow with the embedded
# projection map. This does not invoke any code generator.
set root [file normalize [file join [file dirname [info script]] ../..]]
set script_path [file join $root .upstream drakon_editor]

proc read_file {path} {
    set f [open $path r]
    try {read $f} finally {close $f}
}

proc semantic_target {start vertex_to_node} {
    set pending [list $start]
    set seen [dict create]
    set found {}

    while {[llength $pending] != 0} {
        set current [lindex $pending 0]
        set pending [lrange $pending 1 end]
        if {[dict exists $seen $current]} {
            continue
        }
        dict set seen $current 1

        if {[dict exists $vertex_to_node $current]} {
            lappend found [dict get $vertex_to_node $current]
            continue
        }

        set nexts {}
        gdb eval {
            select dst
            from links
            where src = :current
            order by ordinal
        } {
            lappend nexts $dst
        }
        if {[llength $nexts] == 0} {
            error "Editor semantic path from vertex $start stops at unmapped vertex $current"
        }
        foreach next $nexts {
            lappend pending $next
        }
    }

    set found [lsort -unique $found]
    if {[llength $found] != 1} {
        error "Editor semantic path from vertex $start reaches [llength $found] mapped nodes: $found"
    }
    return [lindex $found 0]
}

proc observed_role {kind ordinal source_rank target_rank} {
    switch -- $kind {
        entry {
            if {$ordinal != 1} {error "Entry has unexpected link ordinal $ordinal"}
            return next
        }
        action {
            if {$ordinal != 1} {error "Action has unexpected link ordinal $ordinal"}
            if {$target_rank < $source_rank} {
                return back
            }
            return next
        }
        return {
            if {$ordinal != 1} {error "Return has unexpected link ordinal $ordinal"}
            return return
        }
        decision {
            if {$ordinal == 1} {return false}
            if {$ordinal == 2} {return true}
            error "Decision has unexpected link ordinal $ordinal"
        }
        loop {
            if {$ordinal == 1} {return loop_exit}
            if {$ordinal == 2} {return loop_body}
            error "Loop has unexpected link ordinal $ordinal"
        }
        exit {
            error "Exit must not have outgoing Editor links"
        }
        default {
            error "Unsupported mapped semantic kind $kind"
        }
    }
}

proc verify_semantic_roundtrip {db} {
    set map_json [$db onecolumn {
        select value
        from diagram_info
        where name = 'drakon-ada/drn-projection-map/v1'
    }]
    if {$map_json eq ""} {
        error "Missing Drakon-ada projection map metadata"
    }

    set mapping [::json::json2dict $map_json]
    if {[dict get $mapping schema] ne "drakon-ada/drn-projection-map/v1"} {
        error "Unexpected projection map schema"
    }

    set node_to_vertex [dict create]
    set vertex_to_node [dict create]
    set kinds [dict create]
    set ranks [dict create]

    foreach node [dict get $mapping nodes] {
        set node_id [dict get $node node_id]
        set item_id [dict get $node item_id]
        set kind [dict get $node semantic_kind]
        set rank [dict get [dict get $node physical] rank]
        set vertex_id [gdb onecolumn {
            select vertex_id
            from vertices
            where item_id = :item_id
        }]
        if {$vertex_id eq ""} {
            error "Mapped node $node_id has no Editor graph vertex"
        }
        if {[dict exists $vertex_to_node $vertex_id]} {
            error "Mapped nodes share Editor graph vertex $vertex_id"
        }
        dict set node_to_vertex $node_id $vertex_id
        dict set vertex_to_node $vertex_id $node_id
        dict set kinds $node_id $kind
        dict set ranks $node_id $rank
    }

    set observed {}
    foreach node [dict get $mapping nodes] {
        set source [dict get $node node_id]
        set kind [dict get $kinds $source]
        set source_vertex [dict get $node_to_vertex $source]
        set source_rank [dict get $ranks $source]

        set hops {}
        gdb eval {
            select ordinal, dst, direction
            from links
            where src = :source_vertex
            order by ordinal
        } {
            lappend hops [list $ordinal $dst $direction]
        }

        if {$kind eq "exit"} {
            if {[llength $hops] != 0} {
                error "Mapped exit $source has outgoing Editor links"
            }
            continue
        }
        if {[llength $hops] == 0} {
            error "Mapped node $source has no outgoing Editor links"
        }

        foreach hop $hops {
            lassign $hop ordinal dst direction
            set target [semantic_target $dst $vertex_to_node]
            set target_rank [dict get $ranks $target]
            set role [observed_role $kind $ordinal $source_rank $target_rank]
            lappend observed [list $source $role $target]
        }
    }

    set expected {}
    foreach edge [dict get $mapping edges] {
        lappend expected [list \
            [dict get $edge from] \
            [dict get $edge role] \
            [dict get $edge to]]
    }

    set expected [lsort $expected]
    set observed [lsort $observed]
    if {$expected ne $observed} {
        error "Projection/Editor semantic mismatch\nexpected: $expected\nobserved: $observed"
    }
}

set lock [read_file [file join $root upstream.lock]]
if {[string trim [exec git -C $script_path rev-parse HEAD]] ne [dict get $lock commit]} {
    error "Upstream commit mismatch"
}
if {[string trim [exec git -C $script_path status --porcelain --untracked-files=no]] ne ""} {
    error "Upstream tracked files are modified"
}

package require msgcat
package require json
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

    verify_semantic_roundtrip db
    db close
} message options]} {
    puts stderr [dict get $options -errorinfo]
    exit 1
}

puts "PASS: pinned DRAKON Editor accepted graph and semantic round-trip matched projection"
