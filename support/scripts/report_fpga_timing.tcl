package require ::quartus::project
package require ::quartus::sta

set project [lindex $argv 0]
project_open $project -revision $project
create_timing_netlist
read_sdc
update_timing_netlist
set report_file [file normalize "output_files/Diablo.timing_corners.rpt"]
file delete -force $report_file
foreach {label model temperature} {
    slow_100C slow 100
    slow_minus40C slow -40
    fast_100C fast 100
    fast_minus40C fast -40
} {
    post_message "Diablo timing corner: $label"
    set_operating_conditions -model $model -temperature $temperature -voltage 1100
    update_timing_netlist
    set header [open $report_file a]
    puts $header "Diablo timing corner: $label"
    close $header
    report_timing -file $report_file -append -npaths 3 -detail full_path
}
delete_timing_netlist
project_close
