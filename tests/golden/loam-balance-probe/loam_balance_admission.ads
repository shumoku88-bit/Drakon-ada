-- Generated from DRAKON and explicit ada metadata. DO NOT EDIT.
package Loam_Balance_Admission with SPARK_Mode => On is
   type Quantity is range -30 .. 30;
   subtype Change_Quantity is Quantity range -10 .. 10;

   procedure Admit_Three_Changes (First : in Change_Quantity; Second : in Change_Quantity; Third : in Change_Quantity; Accepted : out Boolean)
     with Post => Accepted = (First + Second + Third = 0);
end Loam_Balance_Admission;
