-- FLUX Constraint Engine — VHDL
-- FPGA constraint checker, 3-cycle pipeline, 250MHz target
-- INT8 saturated [-127, 127], up to 8 parallel constraints

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity flux_constraint_checker is
    generic (
        NUM_CONSTRAINTS : integer range 1 to 8 := 4;
        DATA_WIDTH      : integer := 8
    );
    port (
        clk          : in  STD_LOGIC;
        rst          : in  STD_LOGIC;
        -- Input
        value_in     : in  SIGNED(DATA_WIDTH-1 downto 0);
        valid_in     : in  STD_LOGIC;
        -- Constraint bounds (registered)
        lo_bounds    : in  SIGNED_ARRAY_8(0 to NUM_CONSTRAINTS-1);
        hi_bounds    : in  SIGNED_ARRAY_8(0 to NUM_CONSTRAINTS-1);
        -- Output
        error_mask   : out STD_LOGIC_VECTOR(NUM_CONSTRAINTS-1 downto 0);
        severity     : out STD_LOGIC_VECTOR(1 downto 0);  -- 00=pass 01=caution 10=warning 11=critical
        violated_cnt : out UNSIGNED(3 downto 0);
        passed       : out STD_LOGIC;
        valid_out    : out STD_LOGIC
    );
end entity;

architecture rtl of flux_constraint_checker is

    type SIGNED_ARRAY_8 is array (natural range <>) of SIGNED(7 downto 0);

    -- Pipeline stage 1: saturate input
    signal sat_value   : SIGNED(7 downto 0);
    signal valid_s1    : STD_LOGIC;

    -- Pipeline stage 2: compare
    signal mask_s2     : STD_LOGIC_VECTOR(NUM_CONSTRAINTS-1 downto 0);
    signal cnt_s2      : UNSIGNED(3 downto 0);
    signal valid_s2    : STD_LOGIC;

    -- Pipeline stage 3: severity
    signal sev_s3      : STD_LOGIC_VECTOR(1 downto 0);
    signal cnt_s3      : UNSIGNED(3 downto 0);

    -- Saturation constant
    constant INT8_MIN : SIGNED(7 downto 0) := to_signed(-127, 8);
    constant INT8_MAX : SIGNED(7 downto 0) := to_signed(127, 8);

begin

    -- Stage 1: Saturate input value to [-127, 127]
    process(clk, rst)
    begin
        if rst = '1' then
            sat_value <= (others => '0');
            valid_s1  <= '0';
        elsif rising_edge(clk) then
            valid_s1 <= valid_in;
            if value_in < INT8_MIN then
                sat_value <= INT8_MIN;
            elsif value_in > INT8_MAX then
                sat_value <= INT8_MAX;
            else
                sat_value <= resize(value_in, 8);
            end if;
        end if;
    end process;

    -- Stage 2: Parallel constraint comparison
    process(clk, rst)
        variable v_mask : STD_LOGIC_VECTOR(NUM_CONSTRAINTS-1 downto 0);
        variable v_cnt  : integer range 0 to 8;
    begin
        if rst = '1' then
            mask_s2  <= (others => '0');
            cnt_s2   <= (others => '0');
            valid_s2 <= '0';
        elsif rising_edge(clk) then
            valid_s2 <= valid_s1;
            v_mask := (others => '0');
            v_cnt  := 0;
            for i in 0 to NUM_CONSTRAINTS-1 loop
                if sat_value < lo_bounds(i) or sat_value > hi_bounds(i) then
                    v_mask(i) := '1';
                    v_cnt := v_cnt + 1;
                end if;
            end loop;
            mask_s2 <= v_mask;
            cnt_s2  <= to_unsigned(v_cnt, 4);
        end if;
    end process;

    -- Stage 3: Compute severity
    process(clk, rst)
        variable nc_div4 : integer;
        variable nc_div2 : integer;
    begin
        if rst = '1' then
            sev_s3      <= "00";
            cnt_s3      <= (others => '0');
            valid_out   <= '0';
        elsif rising_edge(clk) then
            valid_out <= valid_s2;
            cnt_s3    <= cnt_s2;
            nc_div4 := NUM_CONSTRAINTS / 4;
            nc_div2 := NUM_CONSTRAINTS / 2;

            if cnt_s2 = 0 then
                sev_s3 <= "00";  -- Pass
            elsif cnt_s2 <= nc_div4 then
                sev_s3 <= "01";  -- Caution
            elsif cnt_s2 <= nc_div2 then
                sev_s3 <= "10";  -- Warning
            else
                sev_s3 <= "11";  -- Critical
            end if;
        end if;
    end process;

    -- Output assignment
    error_mask   <= mask_s2;
    severity     <= sev_s3;
    violated_cnt <= cnt_s3;
    passed       <= '1' when cnt_s3 = 0 else '0';

end architecture;
