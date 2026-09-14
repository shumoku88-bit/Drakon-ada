# Ada/SPARK movement-slice plugin. New contributions: MIT (see LICENSE).
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

# Deliberately small expression language: no calls, attributes, declarations,
# pragmas or inline control flow. This is not a general Ada parser.
proc expression {text} {
    if {![regexp {^[A-Za-z0-9_ \t\n()+<>=*/.-]+$} $text] ||
        [string first "--" $text] >= 0 ||
        [regexp -nocase {\m(pragma|assume|suppress|goto|raise|with|declare|begin|end|if|loop|return)\M} $text] ||
        [regexp {[A-Za-z0-9_]\s*\(} $text]} {
        error "Unsupported expression: $text"
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
    if {[lsort [dict keys $raw]] ne [lsort $keys]} {error "Unexpected metadata keys"}
    if {[dict get $raw schema] ne "1"} {error "Unsupported metadata schema"}
    if {[dict get $raw profile] ni {Ada SPARK}} {error "Unsupported profile"}
    identifier [dict get $raw package]
    expression [dict get $raw post]
    if {[string trim [dict get $raw post]] eq ""} {error "Empty explicit postcondition"}
    return $raw
}

proc signature {text name} {
    if {[string trim $text] ne ""} {error "Parameters belong in explicit ada metadata"}
    identifier $name
    return [list "" [gen::create_signature procedure {} {} ""]]
}
proc unsupported {args} {error "Unsupported feature in movement slice: $args"}
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
proc literal {text} {return $text}
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
    } {gen::put_callback result $key $value}
    foreach {key value} {
        while_start loop if_start {if } if_end { then} else_start else
        elseif_start {elsif } pass {null;} return_none {return;}
    } {gen::put_callback result $key [list gen_ada::literal $value]}
    gen::put_callback result break {exit;}
    return $result
}

proc generate {db gdb filename} {
    set diagrams [$db eval {select diagram_id from diagrams order by diagram_id}]
    if {[llength $diagrams] != 1} {error "Movement slice requires exactly one diagram"}
    set id [lindex $diagrams 0]
    set meta [metadata $db $id]
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
                    expression $rhs
                }
            }
            if {expression $row(text)}
            beginend - vertical - horizontal - branch - address - junction - arrow - params - comment {}
            default {error "Unsupported icon in movement slice: $row(type)"}
        }
    }
    set cb [callbacks]
    gen::fix_graph_for_diagram $gdb $cb 0 $id
    set functions [gen::generate_functions $db $gdb $cb 1]
    if {[graph::errors_occured]} {error [graph::get_error_list]}
    if {[llength $functions] != 1} {error "Expected one generated procedure"}
    lassign [lindex $functions 0] ignored name signature body
    set pkg [dict get $meta package]
    set decls {}
    foreach decl [dict get $meta declarations] {
        set kind [lindex $decl 0]
        if {$kind eq "integer" && [llength $decl] == 4} {
            lassign $decl kind type low high
            set prefix "type [identifier $type] is"
        } elseif {$kind eq "subtype" && [llength $decl] == 5} {
            lassign $decl kind type base low high
            set prefix "subtype [identifier $type] is [identifier $base]"
        } else {error "Unsupported type declaration: $decl"}
        foreach bound [list $low $high] {
            if {![regexp {^-?(0|[1-9][0-9]*)$} $bound]} {error "Expected integer bound"}
        }
        if {$low > $high} {error "Reversed type bounds"}
        lappend decls "   $prefix range $low .. $high;"
    }
    set params {}
    foreach param [dict get $meta parameters] {
        if {[llength $param] != 3} {error "Expected name, mode, type"}
        lassign $param pname mode type
        if {$mode ni {in out {in out}}} {error "Unsupported parameter mode"}
        lappend params "[identifier $pname] : $mode [identifier $type]"
    }
    if {$params eq {}} {error "Expected explicit parameters"}
    set declaration "procedure $name ([join $params {; }])"
    set aspect ""
    if {[dict get $meta profile] eq "SPARK"} {set aspect " with SPARK_Mode => On"}
    set banner "-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT."
    set spec "$banner\npackage $pkg$aspect is\n[join $decls \n]\n\n   $declaration\n     with Post => [dict get $meta post];\nend $pkg;\n"
    set impl "$banner\npackage body $pkg$aspect is\n   $declaration is\n   begin\n[gen::indent $body 2]\n   end $name;\nend $pkg;\n"
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
