import os
import time
import numpy as np
import pandas
import pandas as pd
import settings as s
import shutil
from pathlib import Path
from analyse_all_programs_report import AnalyseAllPrograms

# init objects
analyse_all_programs_report = AnalyseAllPrograms()
    
# instructions for user
print("--- FMS Cycle Time Analysis --- " + s.version)
print("Determines if each program is running at its shortest cycle.")
print("Export FMS Cycles from TTM for any date range, check 'include complete cycles only'.")
print("Copy exported files to C:\\programcycles")
print()

while(True):
    input("Press Enter to process files...")
    print("Reading exported files...")

    # delete existing reports folder
    if os.path.exists(s.reports_folder):
        shutil.rmtree(s.reports_folder)

    # pandas settings
    pd.set_option('display.max_columns', 18)
    pd.set_option('display.width', 400)

    # read data files, create dataframe of cleaned data
    file_data_appended = []
    file_list = os.listdir(s.program_cycles_folder)
    for file in file_list:
        data = pd.read_excel(s.program_cycles_folder + file)
        file_data_appended.append(data)

    df = pd.concat(file_data_appended, ignore_index=True)
    df = df.drop_duplicates(keep='first')
    df = df.sort_values(by=[s.cycle_start], ascending=False)
    df = df[[s.machine, s.program,s.pallet ,s.part_count ,s.cycle_start,s.cycle_time]]
    df[s.cycle_start] = pd.to_datetime(df[s.cycle_start]).dt.date
    # print(df)

    # create dictionary of dataframes by program name, clean timestamp data
    df_programs = dict()
    for k, v in df.groupby(s.program):
        v = v.reset_index(drop=True)
        v[s.cycle_length_minutes] = pd.to_datetime(v[s.cycle_time],format='%H:%M:%S', errors='coerce')
        v[s.cycle_length_minutes] = (
            round(v[s.cycle_length_minutes].dt.hour*60 +
                  v[s.cycle_length_minutes].dt.minute +
                  v[s.cycle_length_minutes].dt.second/60,2))
        df_programs[k] = v

    # create report structure
    df_programs_keys = list(df_programs.keys())
    programs_found = len(df_programs_keys)
    print(" Programs Found:", programs_found)

    programs_processed = 0
    df_program_groups_dict = dict()
    df_all_programs_report = pd.DataFrame(
        columns=[s.program,
                 s.current_group_cycle,
                 s.current_group_date,
                 s.current_part_count,
                 s.shortest_group_cycle,
                 s.shortest_group_date,
                 s.shortest_part_count,
                 s.longest_group_cycle,
                 s.longest_group_date,
                 s.longest_part_count,])

    # analyze each program
    for program in df_programs_keys:
        # progress count
        programs_processed = programs_processed + 1
        print('\r', "Processing: " + str(int(100 * round(programs_processed/programs_found,2))) + "%", end='')
        time.sleep(.01)

        cycle_count = len(df_programs[program].index)
        newest_cycle = df_programs[program].iloc[0][s.cycle_start]
        oldest_cycle = df_programs[program].iloc[cycle_count-1][s.cycle_start]
        # print("Program: " + program)
        # print("Cycle Count:", cycle_count)
        # print("Newest Cycle:", newest_cycle)
        # print("Oldest Cycle:", oldest_cycle)
        # print()
        # print(df_programs[program])

        # create df for cycle summary and report
        df_program_groups = pd.DataFrame(columns=[s.cycle_group_start_time,
                                                  s.cycle_group_end_time,
                                                  s.median_length,
                                                  s.matching_cycles,
                                                  s.start_index,
                                                  s.end_index,
                                                  s.part_count])

        program_times = dict()
        #cycle_index
        i = 0

        # analyze each cycle, find groups of matching cycles
        while i < cycle_count:
            base_cycle = df_programs[program].iloc[i][s.cycle_length_minutes]
            matches = 0
            matches_dict = dict()
            test_list = list()
            part_count_list = list()
            median_test_cycle = 0

            # add the current cycle and next 4 to a list and find the median
            for j in range(0,cycle_count-i):
                test_cycle = df_programs[program].iloc[i+j][s.cycle_length_minutes]
                test_list.append(test_cycle)
                part_count_list.append(df_programs[program].iloc[i+j][s.part_count])

                if len(test_list) >4:
                    median_test_cycle = np.median(test_list)
                    break;

            # test if all cycles in the list are within range of the median
            for k in range(0, len(test_list)):
                if (test_list[k] < median_test_cycle * s.high_match_limit and
                        test_list[k] > median_test_cycle * s.low_match_limit):
                    matches_dict[i+k] = test_list[k]
                    matches += 1

           # if a pattern is found, add any subsequent matching cycles and record information in the df
            if matches > 4:
                for j in range(5, cycle_count - i - 5):
                    test_cycle = df_programs[program].iloc[i + j][s.cycle_length_minutes]
                    if (test_cycle < median_test_cycle * s.high_match_limit and
                            test_cycle > median_test_cycle * s.low_match_limit):
                        matches_dict[i + j] = test_cycle
                        part_count_list.append(df_programs[program].iloc[i + j][s.part_count])
                        matches += 1
                    else:
                        break

                # summarize information and add to df
                program_times[i] = matches_dict
                cycle_group_start_time = df_programs[program].iloc[i+matches][s.cycle_start]
                cycle_group_end_time = df_programs[program].iloc[i][s.cycle_start]
                median_length = round(np.median(list(matches_dict.values())),2)
                average_part_count = round(np.average(part_count_list),1)
                matching_cycles = matches + 1
                start_index = i
                end_index = i + j
                df_program_groups.loc[i] = (cycle_group_start_time,
                                         cycle_group_end_time,
                                         median_length,
                                         matching_cycles,
                                         start_index,
                                         end_index,
                                         average_part_count)

                # print all match groups
                # print("Cycle Group Start: " + df_programs[program].iloc[i+matches][s.cycle_start])
                # print("Cycle Group End: " + df_programs[program].iloc[i][s.cycle_start])
                # print("Median Length: " + str(df_programs[program].iloc[i][s.cycle_length_minutes]))
                # print("Matching Cycles:", matches)
                # print()

                # skip current matched cycles
                i = i + matches - 1

            else:
                i += 1

        # print(df_programs[program].iloc[0])

        # set data and add to report dataframe
        df_program_groups.reset_index(drop=True, inplace=True)
        if len(df_program_groups.index) > 0:
            current_group_cycle = df_program_groups.iloc[0][s.median_length]
            current_group_cycle_date = df_program_groups.iloc[0][s.cycle_group_start_time]
            current_part_count = df_program_groups.iloc[0][s.part_count]
            shortest_group_cycle = df_program_groups.loc[df_program_groups[s.median_length].idxmin()][s.median_length]
            shortest_group_cycle_date = df_program_groups.loc[df_program_groups[s.median_length].idxmin()][s.cycle_group_start_time]
            shortest_part_count = df_program_groups.loc[df_program_groups[s.median_length].idxmin()][s.part_count]
            longest_group_cycle = df_program_groups.loc[df_program_groups[s.median_length].idxmax()][s.median_length]
            longest_group_cycle_date = df_program_groups.loc[df_program_groups[s.median_length].idxmax()][s.cycle_group_start_time]
            longest_part_count = df_program_groups.loc[df_program_groups[s.median_length].idxmax()][s.part_count]

        # set data to 0 if group isn't found for the program
        else:
            current_group_cycle = 0
            shortest_group_cycle = 0
            longest_group_cycle = 0
            current_part_count = 0
            shortest_part_count = 0
            longest_part_count = 0

        df_all_programs_report.loc[i] = (program,
                                         current_group_cycle,
                                         current_group_cycle_date,
                                         current_part_count,
                                         shortest_group_cycle,
                                         shortest_group_cycle_date,
                                         shortest_part_count,
                                         longest_group_cycle,
                                         longest_group_cycle_date,
                                         longest_part_count)

        # print()
        # print(df_program_groups)
        # input("Press Enter to continue...")

    df_all_programs_report.reset_index(drop = True, inplace=True)
    df_longer_cycles_report = analyse_all_programs_report.find_longer_cycles(df_all_programs_report)
    df_no_groups_programs = df_all_programs_report[df_all_programs_report[s.current_group_cycle] == 0].copy()

    # print("All Programs Report")
    # print(df_all_programs_report)
    # print()
    # print("Longer Cycles Report")
    # print(df_longer_cycles_report)
    # print()
    # print("Programs With No Cycle Groups Found")
    # print(df_no_groups_programs)
    # print()

    report_dict = {'longer cycles': df_longer_cycles_report, 'all programs': df_all_programs_report, 'no groups': df_no_groups_programs}
    Path("C:/programcycles/reports").mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(s.reports_folder + s.reports_file, engine = 'xlsxwriter') as writer:

        for sheetname, df in report_dict.items():  # loop through `dict` of dataframes
            df.to_excel(writer, sheet_name=sheetname)  # send df to writer
            worksheet = writer.sheets[sheetname]  # pull worksheet object
            worksheet.autofit()

    print()
    print("Report saved to: " + s.reports_folder)
    print()
    #df_all_programs_report.to_excel(s.reports_folder + s.all_report_output)
    #df_longer_cycles_report.to_excel(s.longer_cycles_output)
    #df_no_groups_programs.to_excel(s.no_groups_output)
