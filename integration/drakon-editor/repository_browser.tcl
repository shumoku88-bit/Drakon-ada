# Repository Browser extension for DRAKON Editor.
#
# Provides cross-repository diagram browsing and switching in the left pane
# without mutating source files or altering the canonical pinned upstream.

if {[catch {package require Img}]} {
    package provide Img 1.0
}

namespace eval repobrowser {
    variable repo_root ""
    variable catalog_file ""
    variable tree ""
    variable nb ""
    variable status_label ""
    variable node_target ; # array: node_id -> [list abs_path diagram_id type]
    variable icons_loaded 0
    variable img_folder ""
    variable img_diagram ""

    proc get_repo_root {} {
        variable repo_root
        if {$repo_root ne ""} { return $repo_root }
        if {[info exists ::env(DRAKON_REPO_ROOT)] && $::env(DRAKON_REPO_ROOT) ne ""} {
            set repo_root [file normalize $::env(DRAKON_REPO_ROOT)]
            return $repo_root
        }
        global script_path
        set repo_root [file normalize [file join $script_path ".." ".."]]
        return $repo_root
    }

    proc get_catalog_file {} {
        variable catalog_file
        if {$catalog_file ne ""} { return $catalog_file }
        global script_path
        set catalog_file [file normalize [file join $script_path "repository_catalog.json"]]
        return $catalog_file
    }

    proc load_icons {} {
        variable icons_loaded
        variable img_folder
        variable img_diagram
        global script_path

        if {$icons_loaded} { return }

        set folder_gif [file join $script_path "images" "folder.gif"]
        set dia_gif [file join $script_path "images" "diagram.gif"]

        if {[file exists $folder_gif]} {
            set img_folder [image create photo -format GIF -file $folder_gif]
        }
        if {[file exists $dia_gif]} {
            set img_diagram [image create photo -format GIF -file $dia_gif]
        }
        set icons_loaded 1
    }

    proc install_ui {} {
        variable tree
        variable nb
        variable status_label

        load_icons

        # Unpack .root.pnd.left from the main panedwindow
        .root.pnd forget .root.pnd.left

        # Create notebook in .root.pnd
        set nb [ttk::notebook .root.pnd.nb]

        # Create frame for Repository browser
        set repo_frame [ttk::frame .root.pnd.repo -padding "2 2 2 2"]

        # Add tabs: [Repository] [Current file]
        $nb add $repo_frame -text [mc2 "Repository"]
        $nb add .root.pnd.left -text [mc2 "Current file"]

        # Insert notebook into left slot of main panedwindow
        .root.pnd insert 0 $nb

        # --- Repository Browser UI ---
        # Top toolbar
        set bar [ttk::frame $repo_frame.bar]
        ttk::button $bar.refresh -text [mc2 "Refresh"] -command repobrowser::refresh
        set status_label [ttk::label $bar.status -text "Ready" -font main_font]
        pack $bar.refresh -side left -padx 2 -pady 2
        pack $status_label -side left -padx 4 -pady 2 -fill x -expand 1
        pack $bar -fill x -side top

        # Treeview + Scrollbar
        set treeframe [ttk::frame $repo_frame.tf]
        set tree [ttk::treeview $treeframe.tree -selectmode browse]
        ttk::scrollbar $treeframe.vsb -orient vertical -command [list $tree yview]
        $tree configure -yscrollcommand [list $treeframe.vsb set]

        pack $treeframe.vsb -side right -fill y
        pack $tree -side left -fill both -expand 1
        pack $treeframe -fill both -expand 1 -side top

        # Bindings
        bind $tree <<TreeviewSelect>> { repobrowser::on_select }
        bind $tree <Double-1> { repobrowser::on_activate }
        bind $tree <Return> { repobrowser::on_activate }

        # Populate tree
        populate_tree
    }

    proc parse_json_file { filename } {
        if {![file exists $filename]} {
            return ""
        }
        if {![catch {package require json}]} {
            set fp [open $filename r]
            fconfigure $fp -encoding utf-8
            set content [read $fp]
            close $fp
            return [json::json2dict $content]
        }
        return ""
    }

    proc populate_tree {} {
        variable tree
        variable node_target
        variable status_label
        variable img_folder
        variable img_diagram

        array unset node_target

        set cat_file [get_catalog_file]
        if {![file exists $cat_file]} {
            # Try generating on the fly
            run_generator
        }

        # Clear existing items in tree
        foreach child [$tree children {}] {
            $tree delete $child
        }

        set data [parse_json_file $cat_file]
        if {$data eq "" || ![dict exists $data nodes]} {
            $status_label configure -text "Catalog empty"
            return
        }

        set nodes [dict get $data nodes]
        set count 0

        foreach node $nodes {
            set id [dict get $node id]
            set parent [dict get $node parent]
            set text [dict get $node text]
            set ntype [dict get $node type]
            set is_open 0
            if {[dict exists $node open] && [dict get $node open]} {
                set is_open 1
            }

            set img ""
            if {$ntype eq "root" || $ntype eq "group" || $ntype eq "section" || $ntype eq "file"} {
                set img $img_folder
            } elseif {$ntype eq "diagram"} {
                set img $img_diagram
            }

            set abs_path ""
            set dia_id ""
            if {[dict exists $node abs_path]} {
                set abs_path [dict get $node abs_path]
            }
            if {[dict exists $node diagram_id]} {
                set dia_id [dict get $node diagram_id]
            }

            set opts [list -text $text -open $is_open]
            if {$img ne ""} {
                lappend opts -image $img
            }

            if {$parent eq ""} {
                $tree insert {} end -id $id {*}$opts
            } else {
                if {[$tree exists $parent]} {
                    $tree insert $parent end -id $id {*}$opts
                } else {
                    $tree insert {} end -id $id {*}$opts
                }
            }

            if {$abs_path ne ""} {
                set node_target($id) [list $abs_path $dia_id $ntype]
            }
            incr count
        }

        $status_label configure -text "Loaded ($count items)"
    }

    proc run_generator {} {
        set root [get_repo_root]
        set py [file join $root "tools" "repository_browser.py"]
        set cat_file [get_catalog_file]
        if {[file exists $py]} {
            catch {exec python3 $py --root $root --output $cat_file}
        }
    }

    proc refresh {} {
        variable status_label
        $status_label configure -text "Scanning..."
        update
        run_generator
        populate_tree
    }

    proc on_select {} {
        variable tree
        variable node_target
        set sel [$tree selection]
        if {$sel eq ""} { return }
        set id [lindex $sel 0]
        if {![info exists node_target($id)]} { return }

        lassign $node_target($id) abs_path dia_id ntype
        if {$ntype eq "diagram"} {
            open_target $abs_path $dia_id
        }
    }

    proc on_activate {} {
        variable tree
        variable node_target
        set sel [$tree selection]
        if {$sel eq ""} { return }
        set id [lindex $sel 0]
        if {![info exists node_target($id)]} { return }

        lassign $node_target($id) abs_path dia_id ntype
        open_target $abs_path $dia_id
    }

    proc open_target { abs_path dia_id } {
        variable status_label
        set abs_path [file normalize $abs_path]

        if {![file exists $abs_path]} {
            tk_messageBox -icon error -message "File does not exist:\n$abs_path"
            return
        }

        set is_same_file 0
        if {[info exists mod::db_names($ds::db)]} {
            if {[file normalize $mod::db_names($ds::db)] eq $abs_path} {
                set is_same_file 1
            }
        }

        if {!$is_same_file} {
            # Close existing database cleanly
            hl::reset
            if {[info exists mod::db_names($ds::db)]} {
                mod::close $ds::db
            }
            if {![ds::openfile $abs_path]} {
                ds::complain_file $abs_path
                return
            }
        }

        if {$dia_id ne ""} {
            mw::select_dia $dia_id 1
        }

        set dia_name ""
        if {$dia_id ne ""} {
            set dia_name [mwc::get_dia_name $dia_id]
        }
        $status_label configure -text "Open: [file tail $abs_path] / $dia_name"
    }
}
