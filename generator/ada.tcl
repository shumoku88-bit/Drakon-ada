# Ada/SPARK minimal control-flow plugin. New contributions: MIT (see LICENSE).
# Callback/printing patterns adapted from the pinned Public Domain Tcl core:
# generators/go.tcl and scripts/generators.tcl. See NOTICE and docs/licensing.md.
# No dependency on another language emitter.
gen::add_generator Ada gen_ada::generate
gen::add_generator SPARK gen_ada::generate

namespace eval gen_ada {
proc identifier {text} {
    if {![regexp {^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)*$} $text]} {
        error "Invalid Ada identifier: $text"
    }
    return $text
}

proc declaration_catalog {meta} {
    set known {Boolean}
    set arrays {}
    foreach decl [dict get $meta declarations] {
        set kind [lindex $decl 0]
        if {$kind eq "integer" && [llength $decl] == 4} {
            set type [identifier [lindex $decl 1]]
        } elseif {$kind eq "subtype" && [llength $decl] == 5} {
            set type [identifier [lindex $decl 1]]
            set base [identifier [lindex $decl 2]]
            if {[lsearch -exact $known $base] < 0} {
                error "Unknown subtype base: $base"
            }
        } elseif {$kind eq "array" && [llength $decl] == 4} {
            set type [identifier [lindex $decl 1]]
            set index_type [identifier [lindex $decl 2]]
            set element_type [identifier [lindex $decl 3]]
            if {[lsearch -exact $known $index_type] < 0 ||
                [lsearch -exact $known $element_type] < 0} {
                error "Array types must reference earlier declarations"
            }
            lappend arrays $type
        } else {
            error "Unsupported type declaration: $decl"
        }
        if {[lsearch -exact $known $type] >= 0} {
            error "Duplicate type declaration: $type"
        }
        lappend known $type
    }
    return [dict create known $known arrays $arrays]
}

proc indexed_parameters {meta catalog} {
    set arrays [dict get $catalog arrays]
    set result {}
    foreach param [dict get $meta parameters] {
        if {[llength $param] != 3} {error "Expected name, mode, type"}
        lassign $param pname mode type
        identifier $pname
        identifier $type
        if {[lsearch -exact $arrays $type] >= 0} {
            lappend result $pname
        }
    }
    return $result
}

# Deliberately small expression language: no general calls, attributes,
# declarations, pragmas or inline control flow. Schema 3 may read explicitly
# declared array parameters through Ada indexing syntax.
proc expression {text {indexed {}}} {
    if {![regexp {^[A-Za-z0-9_ \t\n()+<>=*/.-]+$} $text] ||
        [string first "--" $text] >= 0 ||
        [regexp -nocase {\m(pragma|assume|suppress|goto|raise|with|declare|begin|end|if|loop|return)\M} $text]} {
        error "Unsupported expression: $text"
    }
    foreach {match word} [regexp -all -inline {([A-Za-z][A-Za-z0-9_]*)\s*\(} $text] {
        if {[string tolower $word] in {not and then or else}} {
            continue
        }
        if {[lsearch -exact $indexed $word] < 0} {
            error "Unsupported expression: $text"
        }
    }
    return $text
}

proc metadata {db diagram_id} {
    set raw [$db onecolumn {
        select value from diagram_info where diagram_id = :diagram_id and name = 'ada'
    }]
    if {$raw eq ""} {error "Missing explicit ada metadata"}
    # dict parsing only, NEVER source/eval/subst metadata.
    set keys {schema profile package declarations parameters post}
    set schema [dict get $raw schema]
    if {$schema eq "2"} {
        lappend keys loop_annotations always_terminates
    } elseif {$schema eq "3"} {
        lappend keys loop_annotations always_terminates locals
    } elseif {$schema ne "1"} {
        error "Unsupported metadata schema"
    }
    if {[lsort [dict keys $raw]] ne [lsort $keys]} {error "Unexpected metadata keys"}
    if {$schema ne "1" && [dict get $raw always_terminates] ni {True False}} {
        error "always_terminates must be explicit True or False"
    }
    if {[dict get $raw profile] ni {Ada SPARK}} {error "Unsupported profile"}
    identifier [dict get $raw package]

    set catalog [declaration_catalog $raw]
    set known [dict get $catalog known]
    set indexed [indexed_parameters $raw $catalog]

    set parameter_names {}
    foreach param [dict get $raw parameters] {
        if {[llength $param] != 3} {error "Expected name, mode, type"}
        lassign $param pname mode type
        set pname [identifier $pname]
        set type [identifier $type]
        if {$mode ni {in out {in out}}} {error "Unsupported parameter mode"}
        if {[lsearch -exact $known $type] < 0} {error "Unknown parameter type: $type"}
        if {[lsearch -exact $parameter_names $pname] >= 0} {error "Duplicate parameter: $pname"}
        lappend parameter_names $pname
    }

    if {$schema eq "3"} {
        set local_names {}
        set arrays [dict get $catalog arrays]
        foreach local [dict get $raw locals] {
            if {[llength $local] != 2} {error "Expected local name and type"}
            lassign $local lname ltype
            set lname [identifier $lname]
            set ltype [identifier $ltype]
            if {[lsearch -exact $known $ltype] < 0} {error "Unknown local type: $ltype"}
            if {[lsearch -exact $arrays $ltype] >= 0} {error "Array locals are not supported"}
            if {[lsearch -exact $parameter_names $lname] >= 0 ||
                [lsearch -exact $local_names $lname] >= 0} {
                error "Duplicate local or parameter name: $lname"
            }
            lappend local_names $lname
        }
    }

    expression [dict get $raw post] $indexed
    if {[string trim [dict get $raw post]] eq ""} {error "Empty explicit postcondition"}
    return $raw
}

proc signature {text name} {
    if {[string trim $text] ne ""} {error "Parameters belong in explicit ada metadata"}
    identifier $name
    return [list "" [gen::create_signature procedure {} {} ""]]
}
proc unsupported {args} {error "Unsupported Ada control-flow feature: $args"}

# Explicit annotations are anchored immediately BEFORE an action icon.
# Verify the anchor remains inside a normalized loop; never guess placement.
proc loop_items {node {depth 0}} {
    set tag [lindex $node 0]
    if {$tag eq "if"} {
        return [concat [loop_items [lindex $node 2] $depth] \
                       [loop_items [lindex $node 3] $depth]]
    }
    if {$tag eq "loop"} {incr depth}
    set result {}
    foreach child [lrange $node 1 end] {
        if {[string is integer -strict $child]} {
            if {$depth > 0} {lappend result $child}
        } elseif {$child ni {break continue}} {
            set result [concat $result [loop_items $child $depth]]
        }
    }
    return $result
}
proc inspect_tree {tree name} {
    variable annotation_ids
    set inside [loop_items $tree]
    foreach id $annotation_ids {
        if {[lsearch -exact $inside $id] < 0} {
            error "Loop annotation anchor $id is not inside a normalized loop in $name"
        }
    }
}
proc annotate {db gdb id meta indexed} {
    variable annotation_ids
    set annotation_ids {}
    if {[dict get $meta schema] eq "1"} {return}
    set annotations [dict get $meta loop_annotations]
    if {[llength $annotations] != 2 * [dict size $annotations]} {
        error "Duplicate loop annotation anchors"
    }
    dict for {anchor annotation} $annotations {
        if {![string is integer -strict $anchor] || $anchor <= 0} {
            error "Invalid loop annotation anchor"
        }
        if {[$db onecolumn {select type from items where diagram_id = :id and item_id = :anchor}] ne "action"} {
            error "Loop annotation anchor must be an action icon"
        }
        if {[lsort [dict keys $annotation]] ne {invariant variant}} {
            error "Expected explicit invariant and variant"
        }
        set invariant [expression [dict get $annotation invariant] $indexed]
        if {[string trim $invariant] eq ""} {error "Empty loop invariant"}
        set variant [dict get $annotation variant]
        if {[llength $variant] != 2 || [lindex $variant 0] ni {Increases Decreases}} {
            error "Expected variant direction and identifier"
        }
        lassign $variant direction measure
        identifier $measure
        set prefix "pragma Loop_Invariant ($invariant);\npragma Loop_Variant ($direction => $measure);\n"
        if {[$gdb onecolumn {select count(*) from vertices where diagram_id = :id and item_id = :anchor}] != 1} {
            error "Ambiguous loop annotation anchor"
        }
        $gdb eval {update vertices set text = :prefix || text where diagram_id = :id and item_id = :anchor}
        lappend annotation_ids $anchor
    }
}
proc assign {left right} {return "$left := $right;"}
proc compare {left right} {return "$left = $right"}
proc negate {value} {return "not ($value)"}
proc conjunction {left right} {return "($left) and then ($right)"}
proc disjunction {left right} {return "($left) or else ($right)"}
proc comment {text} {return "-- $text"}
proc loop_close {output depth} {
    upvar 1 $output result
    lappend result "[gen::make_indent $depth]end loop;"
}
proc if_close {output depth} {
    upvar 1 $output result
    lappend result "[gen::make_indent $depth]end if;"
}
# Upstream invokes callbacks as a single command name, not a Tcl command prefix.
foreach {key value} {
    while_start loop if_start {if } if_end { then} else_start else
    elseif_start {elsif } pass {null;} return_none {return;}
} {proc syntax_$key {} [list return $value]}
proc callbacks {} {
    # Optional callbacks must be absent unless implemented.
    set result {}
    foreach {key value} {
        assign gen_ada::assign compare gen_ada::compare compare2 gen_ada::compare
        not gen_ada::negate and gen_ada::conjunction or gen_ada::disjunction
        comment gen_ada::comment block_close gen_ada::loop_close
        if_block_end gen_ada::if_close signature gen_ada::signature
        body gen_ada::unsupported enforce_nogoto gen_ada::unsupported
        shelf gen_ada::unsupported declare gen_ada::unsupported
        inspect_tree gen_ada::inspect_tree
    } {gen::put_callback result $key $value}
    foreach {key value} {
        while_start loop if_start {if } if_end { then} else_start else
        elseif_start {elsif } pass {null;} return_none {return;}
    } {gen::put_callback result $key gen_ada::syntax_$key}
    gen::put_callback result break {exit;}
    return $result
}

proc generate {db gdb filename} {
    set diagrams [$db eval {select diagram_id from diagrams order by diagram_id}]
    if {[llength $diagrams] != 1} {error "Expected exactly one diagram"}
    set id [lindex $diagrams 0]
    set meta [metadata $db $id]
    set catalog [declaration_catalog $meta]
    set known [dict get $catalog known]
    set indexed [indexed_parameters $meta $catalog]
    set language [$db onecolumn {select value from info where key = 'language'}]
    if {$language ne [dict get $meta profile]} {error "Language/profile mismatch"}
    if {![mwc::is_drakon $id]} {error "Expected a DRAKON diagram"}
    # Actions are assignments, not an escape hatch for hidden control flow.
    $db eval {select type, text from items where diagram_id = :id} row {
        switch -- $row(type) {
            action {
                foreach line [split $row(text) "\n"] {
                    if {![regexp {^\s*([A-Za-z][A-Za-z0-9_]*)\s*:=\s*(.+);\s*$} $line -> lhs rhs]} {
                        error "Expected one assignment per action line: $line"
                    }
                    identifier $lhs
                    expression $rhs $indexed
                }
            }
            if {expression $row(text) $indexed}
            beginend - vertical - horizontal - branch - address - junction - arrow - params - comment {}
            default {error "Unsupported Ada icon: $row(type)"}
        }
    }
    annotate $db $gdb $id $meta $indexed
    set cb [callbacks]
    gen::fix_graph_for_diagram $gdb $cb 0 $id
    set functions [gen::generate_functions $db $gdb $cb 1]
    if {[graph::errors_occured]} {error [graph::get_error_list]}
    if {[llength $functions] != 1} {error "Expected one generated procedure"}
    lassign [lindex $functions 0] ignored name signature body
    set pkg [dict get $meta package]
    set decls {}
    set emitted {Boolean}
    foreach decl [dict get $meta declarations] {
        set kind [lindex $decl 0]
        if {$kind eq "integer" && [llength $decl] == 4} {
            lassign $decl kind type low high
            set type [identifier $type]
            foreach bound [list $low $high] {
                if {![regexp {^-?(0|[1-9][0-9]*)$} $bound]} {error "Expected integer bound"}
            }
            if {$low > $high} {error "Reversed type bounds"}
            lappend decls "   type $type is range $low .. $high;"
        } elseif {$kind eq "subtype" && [llength $decl] == 5} {
            lassign $decl kind type base low high
            set type [identifier $type]
            set base [identifier $base]
            if {[lsearch -exact $emitted $base] < 0} {error "Unknown subtype base: $base"}
            foreach bound [list $low $high] {
                if {![regexp {^-?(0|[1-9][0-9]*)$} $bound]} {error "Expected integer bound"}
            }
            if {$low > $high} {error "Reversed type bounds"}
            lappend decls "   subtype $type is $base range $low .. $high;"
        } elseif {$kind eq "array" && [llength $decl] == 4} {
            lassign $decl kind type index_type element_type
            set type [identifier $type]
            set index_type [identifier $index_type]
            set element_type [identifier $element_type]
            if {[lsearch -exact $emitted $index_type] < 0 ||
                [lsearch -exact $emitted $element_type] < 0} {
                error "Array types must reference earlier declarations"
            }
            lappend decls "   type $type is array ($index_type) of $element_type;"
        } else {
            error "Unsupported type declaration: $decl"
        }
        lappend emitted $type
    }

    set params {}
    foreach param [dict get $meta parameters] {
        if {[llength $param] != 3} {error "Expected name, mode, type"}
        lassign $param pname mode type
        set pname [identifier $pname]
        set type [identifier $type]
        if {$mode ni {in out {in out}}} {error "Unsupported parameter mode"}
        if {[lsearch -exact $known $type] < 0} {error "Unknown parameter type: $type"}
        lappend params "$pname : $mode $type"
    }
    if {$params eq {}} {error "Expected explicit parameters"}
    set declaration "procedure $name ([join $params {; }])"

    set locals {}
    if {[dict get $meta schema] eq "3"} {
        foreach local [dict get $meta locals] {
            lassign $local lname ltype
            set lname [identifier $lname]
            set ltype [identifier $ltype]
            lappend locals "      $lname : $ltype;"
        }
    }
    set local_block ""
    if {$locals ne {}} {
        set local_block "\n[join $locals \n]"
    }

    set aspect ""
    if {[dict get $meta profile] eq "SPARK"} {set aspect " with SPARK_Mode => On"}
    set termination ""
    if {[dict get $meta schema] ne "1"} {
        set termination ", Always_Terminates => [dict get $meta always_terminates]"
    }
    set banner "-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT."
    set spec "$banner\npackage $pkg$aspect is\n[join $decls \n]\n\n   $declaration\n     with Post => [dict get $meta post]$termination;\nend $pkg;\n"
    set impl "$banner\npackage body $pkg$aspect is\n   $declaration is$local_block\n   begin\n[gen::indent $body 2]\n   end $name;\nend $pkg;\n"
    foreach {extension content} [list ads $spec adb $impl] {
        set path [file join [file dirname $filename] [string tolower $pkg].$extension]
        set f [open $path w]
        try {
            fconfigure $f -encoding utf-8 -translation lf
            puts -nonewline $f $content
        } finally {close $f}
    }
}
}
